"""Strangler-Fig facade delegating SpecKit lifecycle queries and transitions to Ring 2."""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from alos.adapters.outbound.speckit import SpecKitFilesystemRepository
from alos.application.use_cases.speckit_lifecycle import SpecKitLifecycleUseCase
from alos.domain.models.speckit import InvalidStateTransitionError, LifecycleState
from alos.domain.services.lifecycle_fsm import SpecKitLifecycleFSM
from alos.integrations.speckit.plugins import SpecKitPluginRegistry

__all__ = ["InvalidStateTransitionError", "LifecycleState", "SpecKitLifecycleManager"]


class SpecKitLifecycleManager:
    """Backwards-compatible facade delegating lifecycle operations to SpecKitLifecycleUseCase."""

    VALID_TRANSITIONS: ClassVar[dict[LifecycleState, frozenset[LifecycleState]]] = (
        SpecKitLifecycleFSM.VALID_TRANSITIONS
    )

    def __init__(
        self,
        root_dir: Path | None = None,
        plugin_registry: SpecKitPluginRegistry | None = None,
    ) -> None:
        self.root_dir = root_dir.resolve() if root_dir else Path.cwd().resolve()
        self.specs_dir = self.root_dir / "specs"
        self.repo = SpecKitFilesystemRepository(root_dir=self.root_dir)
        self.records_dir = self.repo.records_dir
        self.plugin_registry = (
            plugin_registry if plugin_registry is not None else SpecKitPluginRegistry.get_instance()
        )
        self._use_case = SpecKitLifecycleUseCase(repo=self.repo, hooks=self.plugin_registry)

    def _get_record_path(self, feature_name: str) -> Path:
        return self.repo._path(feature_name)

    def get_status(self, feature_name: str) -> dict[str, Any]:
        """Retrieve current lifecycle status and history for a given feature spec."""
        return self._use_case.get_status(feature_name)

    def transition_state(
        self,
        feature_name: str,
        target_state: str | LifecycleState,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Transition feature specification to target lifecycle state."""
        return self._use_case.transition_state(feature_name, target_state, reason=reason)

    def list_features(self, state_filter: str | None = None) -> list[dict[str, Any]]:
        """List feature specifications with their lifecycle status."""
        if not self.specs_dir.exists():
            return []
        names = [
            child.name
            for child in self.specs_dir.iterdir()
            if child.is_dir() and child.name not in ("archive", "personas")
        ]
        return self._use_case.list_features(names, state_filter=state_filter)
