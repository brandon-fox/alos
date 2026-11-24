"""RED-first unit tests for pure SpecKitLifecycleUseCase and Strangler-Fig shims."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from alos.application.ports.outbound import SpecKitRepositoryPort
from alos.application.use_cases.speckit_lifecycle import SpecKitLifecycleUseCase
from alos.domain.models.speckit import (
    InvalidStateTransitionError,
    LifecycleRecord,
    LifecycleState,
)
from alos.integrations.speckit.lifecycle import SpecKitLifecycleManager


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
