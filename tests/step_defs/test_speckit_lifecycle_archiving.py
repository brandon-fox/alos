"""Step definitions for speckit_lifecycle_archiving.feature."""

import json
from pathlib import Path
from typing import Any

from pytest_bdd import given, parsers, scenarios, then, when

from alos.integrations.speckit.archiver import SpecKitArchiver
from alos.integrations.speckit.lifecycle import (
    InvalidStateTransitionError,
    LifecycleState,
    SpecKitLifecycleManager,
)
from alos.integrations.speckit.plugins import SpecKitPluginRegistry

scenarios("../features/speckit_lifecycle_archiving.feature")


@given(parsers.parse('a feature spec "{spec_id}" in state "{initial_state}"'))
def step_feature_spec_state(
    tmp_path: Path, bdd_context: dict[str, Any], spec_id: str, initial_state: str
) -> None:
    specs_dir = tmp_path / "specs"
    spec_folder = specs_dir / spec_id
    spec_folder.mkdir(parents=True, exist_ok=True)
    (spec_folder / "spec.md").write_text(f"# {spec_id}\nState: {initial_state}\n", encoding="utf-8")

    manager = SpecKitLifecycleManager(root_dir=tmp_path)
    if initial_state == "in_progress":
        manager.transition_state(spec_id, LifecycleState.IN_PROGRESS)
    elif initial_state == "approved":
        manager.transition_state(spec_id, LifecycleState.IN_PROGRESS)
        manager.transition_state(spec_id, LifecycleState.APPROVED)
    elif initial_state == "completed":
        manager.transition_state(spec_id, LifecycleState.IN_PROGRESS)
        manager.transition_state(spec_id, LifecycleState.APPROVED)
        manager.transition_state(spec_id, LifecycleState.COMPLETED)

    bdd_context["tmp_root"] = tmp_path
    bdd_context["spec_id"] = spec_id
    bdd_context["manager"] = manager


@when(parsers.parse('I transition the spec state to "{new_state}"'))
def step_transition_state(bdd_context: dict[str, Any], new_state: str) -> None:
    manager: SpecKitLifecycleManager = bdd_context["manager"]
    spec_id = bdd_context["spec_id"]
    manager.transition_state(spec_id, LifecycleState(new_state))


@then(parsers.parse('the current state of the spec should be "{expected_state}"'))
def step_verify_state(bdd_context: dict[str, Any], expected_state: str) -> None:
    manager: SpecKitLifecycleManager = bdd_context["manager"]
    spec_id = bdd_context["spec_id"]
    status = manager.get_status(spec_id)
    assert status["current_state"] == expected_state


@then("the lifecycle transition history should record the change")
def step_verify_history(bdd_context: dict[str, Any]) -> None:
    manager: SpecKitLifecycleManager = bdd_context["manager"]
    spec_id = bdd_context["spec_id"]
    status = manager.get_status(spec_id)
    assert len(status["history"]) >= 1


@when(parsers.parse('I attempt an invalid transition directly to "{invalid_state}"'))
def step_attempt_invalid_transition(bdd_context: dict[str, Any], invalid_state: str) -> None:
    manager: SpecKitLifecycleManager = bdd_context["manager"]
    spec_id = bdd_context["spec_id"]
    error = None
    try:
        manager.transition_state(spec_id, LifecycleState(invalid_state))
    except InvalidStateTransitionError as e:
        error = e
    bdd_context["error"] = error


@then("an InvalidStateTransitionError should be raised")
def step_verify_error_raised(bdd_context: dict[str, Any]) -> None:
    assert bdd_context.get("error") is not None
    assert isinstance(bdd_context["error"], InvalidStateTransitionError)


@then(parsers.parse('the spec state should remain "{expected_state}"'))
def step_verify_state_remains(bdd_context: dict[str, Any], expected_state: str) -> None:
    manager: SpecKitLifecycleManager = bdd_context["manager"]
    spec_id = bdd_context["spec_id"]
    status = manager.get_status(spec_id)
    assert status["current_state"] == expected_state


@when(parsers.parse('I run the archive operation for feature "{spec_id}"'))
def step_run_archive(bdd_context: dict[str, Any], spec_id: str) -> None:
    tmp_root: Path = bdd_context["tmp_root"]
    archiver = SpecKitArchiver(root_dir=tmp_root)
    archiver.archive_feature(spec_id)


@then(parsers.parse('the feature folder should be moved to "{archived_path}"'))
def step_verify_archived_folder(bdd_context: dict[str, Any], archived_path: str) -> None:
    tmp_root: Path = bdd_context["tmp_root"]
    spec_id = bdd_context["spec_id"]
    expected = tmp_root / "specs" / "archive" / spec_id
    assert expected.exists()


@then(parsers.parse('"{index_path}" should contain an entry for "{spec_id}"'))
def step_verify_archive_index(bdd_context: dict[str, Any], index_path: str, spec_id: str) -> None:
    tmp_root: Path = bdd_context["tmp_root"]
    idx_file = tmp_root / "specs" / "archive" / "archive-index.json"
    assert idx_file.exists()
    data = json.loads(idx_file.read_text(encoding="utf-8"))
    assert spec_id in data


@given(parsers.parse('an archived feature "{spec_id}" in "{archive_folder}"'))
def step_archived_feature(
    tmp_path: Path, bdd_context: dict[str, Any], spec_id: str, archive_folder: str
) -> None:
    specs_dir = tmp_path / "specs"
    archive_dir = specs_dir / "archive"
    target_folder = archive_dir / spec_id
    target_folder.mkdir(parents=True, exist_ok=True)
    (target_folder / "spec.md").write_text(f"# {spec_id}\nState: completed\n", encoding="utf-8")

    idx_file = archive_dir / "archive-index.json"
    idx_file.write_text(json.dumps({spec_id: {"archived_at": "2026-08-01"}}), encoding="utf-8")

    bdd_context["tmp_root"] = tmp_path
    bdd_context["spec_id"] = spec_id


@when(parsers.parse('I run the restore operation for feature "{spec_id}"'))
def step_run_restore(bdd_context: dict[str, Any], spec_id: str) -> None:
    tmp_root: Path = bdd_context["tmp_root"]
    archiver = SpecKitArchiver(root_dir=tmp_root)
    archiver.restore_feature(spec_id)


@then(parsers.parse('the feature folder should be restored to "{restored_path}"'))
def step_verify_restored_folder(bdd_context: dict[str, Any], restored_path: str) -> None:
    tmp_root: Path = bdd_context["tmp_root"]
    spec_id = bdd_context["spec_id"]
    restored = tmp_root / "specs" / spec_id
    assert restored.exists()


@then(parsers.parse('the entry in "{index_path}" should be removed'))
def step_verify_index_entry_removed(bdd_context: dict[str, Any], index_path: str) -> None:
    tmp_root: Path = bdd_context["tmp_root"]
    spec_id = bdd_context["spec_id"]
    idx_file = tmp_root / "specs" / "archive" / "archive-index.json"
    if idx_file.exists():
        data = json.loads(idx_file.read_text(encoding="utf-8"))
        assert spec_id not in data


@given(parsers.parse('a registered plugin hook for "{hook_name}"'))
def step_registered_plugin_hook(
    tmp_path: Path, bdd_context: dict[str, Any], hook_name: str
) -> None:
    SpecKitPluginRegistry.reset_instance()
    registry = SpecKitPluginRegistry.get_instance()
    events_triggered = []

    def sample_hook(**kwargs: Any) -> None:
        events_triggered.append(kwargs)

    registry.register_hook(hook_name, sample_hook)

    specs_dir = tmp_path / "specs"
    spec_folder = specs_dir / "027-speckit-lifecycle-archiving"
    spec_folder.mkdir(parents=True, exist_ok=True)
    (spec_folder / "spec.md").write_text("# Spec", encoding="utf-8")

    manager = SpecKitLifecycleManager(root_dir=tmp_path)

    bdd_context["manager"] = manager
    bdd_context["events_triggered"] = events_triggered
    bdd_context["spec_id"] = "027-speckit-lifecycle-archiving"


@when("a spec state transition occurs")
def step_state_transition_occurs(bdd_context: dict[str, Any]) -> None:
    manager: SpecKitLifecycleManager = bdd_context["manager"]
    spec_id = bdd_context["spec_id"]
    manager.transition_state(spec_id, LifecycleState.IN_PROGRESS)


@then("the plugin hook should be invoked with transition details")
def step_verify_plugin_hook_invoked(bdd_context: dict[str, Any]) -> None:
    events_triggered = bdd_context["events_triggered"]
    assert len(events_triggered) == 1
    assert events_triggered[0]["target_state"] == LifecycleState.IN_PROGRESS.value
