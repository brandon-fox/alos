"""RED-first unit tests for pure SpecKitLifecycleUseCase and Strangler-Fig shims."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from alos.application.ports.outbound import SpecKitRepositoryPort
from alos.application.use_cases.speckit_lifecycle import (
    SpecKitArchiveUseCase,
    SpecKitLifecycleUseCase,
)
from alos.domain.models.speckit import (
    InvalidStateTransitionError,
    LifecycleRecord,
    LifecycleState,
)
from alos.integrations.speckit.archiver import SpecKitArchiver
from alos.integrations.speckit.lifecycle import SpecKitLifecycleManager
from alos.integrations.speckit.plugins import SpecKitPluginRegistry


class _MemoryRepo(SpecKitRepositoryPort):
    def __init__(self) -> None:
        self.records: dict[str, LifecycleRecord] = {}

    def load_record(self, feature_name: str) -> LifecycleRecord:
        return self.records.get(feature_name, LifecycleRecord(feature_name=feature_name))

    def save_record(self, record: LifecycleRecord) -> None:
        self.records[record.feature_name] = record


class _HookSpy:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def dispatch_event(self, event_name: str, **kwargs: Any) -> list[Any]:
        self.events.append((event_name, kwargs))
        return []


@pytest.mark.mocked
def test_speckit_lifecycle_use_case_isolated_di_and_fsm(tmp_path: Path) -> None:
    """Verify SpecKitLifecycleUseCase uses injected repo and hook dispatcher without I/O."""
    repo, hooks = _MemoryRepo(), _HookSpy()
    uc = SpecKitLifecycleUseCase(repo=repo, hooks=hooks)

    status = uc.get_status("099-feat")
    assert status["current_state"] == "draft" and not hooks.events

    updated = uc.transition_state("099-feat", LifecycleState.IN_PROGRESS, reason="Start work")
    assert updated["current_state"] == "in_progress"
    assert [name for name, _ in hooks.events] == [
        "pre_lifecycle_transition",
        "on_lifecycle_transition",
        "post_lifecycle_transition",
    ]
    with pytest.raises(InvalidStateTransitionError):
        uc.transition_state("099-feat", LifecycleState.ARCHIVED)

    features = uc.list_features(["099-feat", "100-other"], state_filter="in_progress")
    assert [f["feature_name"] for f in features] == ["099-feat"]
    assert uc.list_features(["099-feat", "100-other"])[1]["current_state"] == "draft"

    mgr = SpecKitLifecycleManager(root_dir=tmp_path)
    mgr.transition_state("099-feat", "approved")
    assert mgr.get_status("099-feat")["current_state"] == "approved"


@pytest.mark.mocked
def test_speckit_archive_use_case_isolated_di_and_facade(tmp_path: Path) -> None:
    """Verify SpecKitArchiveUseCase archives, restores, and uses injected hook registries."""
    specs_dir = tmp_path / "specs"
    feat_dir = specs_dir / "088-demo"
    feat_dir.mkdir(parents=True)
    (feat_dir / "spec.md").write_text("# Demo", encoding="utf-8")

    repo, hooks = _MemoryRepo(), _HookSpy()
    lifecycle = SpecKitLifecycleUseCase(repo=repo, hooks=hooks)
    archiver_uc = SpecKitArchiveUseCase(lifecycle=lifecycle, specs_dir=specs_dir, hooks=hooks)

    with pytest.raises(FileNotFoundError):
        archiver_uc.archive_feature("missing")
    with pytest.raises(FileNotFoundError):
        archiver_uc.restore_feature("missing")

    info = archiver_uc.archive_feature("088-demo")
    assert info["state_at_archive"] == "archived" and len(archiver_uc.list_archived_features()) == 1
    assert repo.load_record("088-demo").current_state == LifecycleState.ARCHIVED

    restored = archiver_uc.restore_feature("088-demo")
    assert restored["feature_name"] == "088-demo" and not archiver_uc.list_archived_features()
    assert repo.load_record("088-demo").current_state == LifecycleState.DRAFT

    archiver_uc.archive_index_path.write_text("{corrupt", encoding="utf-8")
    assert archiver_uc.list_archived_features() == []

    custom_reg = SpecKitPluginRegistry()
    events: list[str] = []
    custom_reg.register_hook("on_archive", lambda **kw: events.append(str(kw["feature_name"])))
    facade = SpecKitArchiver(root_dir=tmp_path, plugin_registry=custom_reg)
    facade.archive_feature("088-demo")
    assert (
        events == ["088-demo"] and facade.restore_feature("088-demo")["feature_name"] == "088-demo"
    )
