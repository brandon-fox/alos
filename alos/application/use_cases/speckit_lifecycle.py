"""Ring 2 pure application use case for SpecKit specification lifecycle management."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol

from alos.application.ports.outbound import SpecKitRepositoryPort
from alos.domain.models.speckit import LifecycleState
from alos.domain.services.lifecycle_fsm import SpecKitLifecycleFSM

_Map = dict[str, Any]


class LifecycleHookDispatcher(Protocol):
    """Port for dispatching lifecycle event hooks without global singleton state."""

    def dispatch_event(self, event_name: str, **kwargs: Any) -> list[Any]:
        """Dispatch a lifecycle event and return registered callback outputs."""


class SpecKitLifecycleUseCase:
    """Pure Ring 2 use case orchestrating SpecKit lifecycle transitions via ports."""

    def __init__(
        self,
        repo: SpecKitRepositoryPort,
        hooks: LifecycleHookDispatcher | None = None,
    ) -> None:
        self.repo = repo
        self.hooks = hooks

    def _emit(self, event_name: str, **kwargs: Any) -> None:
        if self.hooks is not None:
            self.hooks.dispatch_event(event_name, **kwargs)

    def get_status(self, feature_name: str) -> _Map:
        """Return serialized LifecycleRecord dict for feature_name via SpecKitRepositoryPort."""
        return self.repo.load_record(feature_name).model_dump(mode="json")

    def transition_state(
        self,
        feature_name: str,
        target_state: str | LifecycleState,
        reason: str | None = None,
    ) -> _Map:
        """Validate transition with SpecKitLifecycleFSM, persist, and dispatch hooks."""
        current = self.repo.load_record(feature_name)
        target = SpecKitLifecycleFSM.validate_transition(
            feature_name, current.current_state, target_state
        )
        event_meta = {
            "feature_name": feature_name,
            "current_state": current.current_state.value,
            "target_state": target.value,
        }
        self._emit("pre_lifecycle_transition", **event_meta)
        updated = SpecKitLifecycleFSM.apply_transition(current, target, reason=reason or "")
        self.repo.save_record(updated)
        self._emit("on_lifecycle_transition", **event_meta)
        self._emit("post_lifecycle_transition", **event_meta)
        return updated.model_dump(mode="json")

    def list_features(
        self, feature_names: Iterable[str], state_filter: str | None = None
    ) -> list[_Map]:
        """Return lifecycle records for named features, optionally filtered by state."""
        results: list[_Map] = []
        for name in feature_names:
            record = self.get_status(name)
            if state_filter is None or record["current_state"] == state_filter:
                results.append(record)
        return results
