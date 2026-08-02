"""Unit and integration tests for SpecKit lifecycle and archiving integrations and plugins."""

from pathlib import Path
from unittest.mock import patch

import pytest

from alos.integrations.speckit.archiver import SpecKitArchiver
from alos.integrations.speckit.lifecycle import (
    InvalidStateTransitionError,
    LifecycleState,
    SpecKitLifecycleManager,
)
from alos.integrations.speckit.plugins import SpecKitPluginRegistry


@pytest.fixture
def test_env(tmp_path: Path):
    """Setup temporary root environment with specs directory structure."""
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir(parents=True, exist_ok=True)
    specify_dir = tmp_path / ".specify"
    specify_dir.mkdir(parents=True, exist_ok=True)

    dummy_feature = specs_dir / "099-test-feature"
    dummy_feature.mkdir(parents=True, exist_ok=True)
    (dummy_feature / "spec.md").write_text("# Test Spec", encoding="utf-8")

    SpecKitPluginRegistry.reset_instance()
    return tmp_path


def test_lifecycle_manager_initial_status(test_env: Path) -> None:
    manager = SpecKitLifecycleManager(root_dir=test_env)
    status = manager.get_status("099-test-feature")
    assert status["feature_name"] == "099-test-feature"
    assert status["current_state"] == LifecycleState.DRAFT.value
    assert len(status["history"]) >= 1


def test_lifecycle_valid_transitions(test_env: Path) -> None:
    manager = SpecKitLifecycleManager(root_dir=test_env)
    feature = "099-test-feature"

    res1 = manager.transition_state(feature, LifecycleState.IN_PROGRESS)
    assert res1["current_state"] == LifecycleState.IN_PROGRESS.value

    res2 = manager.transition_state(feature, LifecycleState.APPROVED)
    assert res2["current_state"] == LifecycleState.APPROVED.value

    res3 = manager.transition_state(feature, LifecycleState.COMPLETED)
    assert res3["current_state"] == LifecycleState.COMPLETED.value


def test_lifecycle_invalid_transition(test_env: Path) -> None:
    manager = SpecKitLifecycleManager(root_dir=test_env)
    feature = "099-test-feature"

    with pytest.raises(InvalidStateTransitionError):
        manager.transition_state(feature, LifecycleState.ARCHIVED)


def test_plugin_registry_hooks(test_env: Path) -> None:
    registry = SpecKitPluginRegistry.get_instance()
    events_triggered = []

    def sample_hook(**kwargs):
        events_triggered.append(kwargs)

    registry.register_hook("on_lifecycle_transition", sample_hook)

    manager = SpecKitLifecycleManager(root_dir=test_env)
    manager.transition_state("099-test-feature", LifecycleState.IN_PROGRESS)

    assert len(events_triggered) == 1
    assert events_triggered[0]["target_state"] == LifecycleState.IN_PROGRESS.value


def test_archiver_archive_and_restore(test_env: Path) -> None:
    archiver = SpecKitArchiver(root_dir=test_env)
    feature = "099-test-feature"

    # Archive feature
    archive_info = archiver.archive_feature(feature)
    assert archive_info["feature_name"] == feature
    assert not (test_env / "specs" / feature).exists()
    assert (test_env / "specs" / "archive" / feature).exists()
    assert (test_env / "specs" / "archive" / "archive-index.json").exists()

    archived_list = archiver.list_archived_features()
    assert len(archived_list) == 1
    assert archived_list[0]["feature_name"] == feature

    # Restore feature
    restore_info = archiver.restore_feature(feature)
    assert restore_info["feature_name"] == feature
    assert (test_env / "specs" / feature).exists()
    assert not (test_env / "specs" / "archive" / feature).exists()

    assert len(archiver.list_archived_features()) == 0


def test_cli_subcommands(test_env: Path) -> None:
    from alos.cli import main

    test_args = [
        "alos",
        "speckit",
        "lifecycle",
        "--feature",
        "099-test-feature",
        "--action",
        "status",
    ]
    with patch("sys.argv", test_args):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
