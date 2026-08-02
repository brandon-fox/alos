"""SpecKit lifecycle manager for tracking specification status and enforcing transitions."""

import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar

from alos.integrations.speckit.plugins import SpecKitPluginRegistry


class LifecycleState(str, Enum):
    """Supported lifecycle states for a SpecKit specification."""

    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    APPROVED = "approved"
    COMPLETED = "completed"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class InvalidStateTransitionError(ValueError):
    """Exception raised when an invalid lifecycle state transition is attempted."""

    pass


class SpecKitLifecycleManager:
    """Manager for querying and transitioning feature specification lifecycle states."""

    VALID_TRANSITIONS: ClassVar[dict[LifecycleState, set[LifecycleState]]] = {
        LifecycleState.DRAFT: {
            LifecycleState.IN_PROGRESS,
            LifecycleState.APPROVED,
            LifecycleState.DEPRECATED,
        },
        LifecycleState.IN_PROGRESS: {
            LifecycleState.APPROVED,
            LifecycleState.DRAFT,
            LifecycleState.DEPRECATED,
        },
        LifecycleState.APPROVED: {
            LifecycleState.COMPLETED,
            LifecycleState.DEPRECATED,
        },
        LifecycleState.COMPLETED: {
            LifecycleState.ARCHIVED,
            LifecycleState.DEPRECATED,
        },
        LifecycleState.DEPRECATED: {
            LifecycleState.ARCHIVED,
            LifecycleState.DRAFT,
        },
        LifecycleState.ARCHIVED: {
            LifecycleState.DRAFT,
            LifecycleState.COMPLETED,
        },
    }

    def __init__(self, root_dir: Path | None = None) -> None:
        self.root_dir = root_dir.resolve() if root_dir else Path.cwd().resolve()
        self.specs_dir = self.root_dir / "specs"
        self.records_dir = self.root_dir / ".specify" / "lifecycle_records"
        self.records_dir.mkdir(parents=True, exist_ok=True)
        self.plugin_registry = SpecKitPluginRegistry.get_instance()

    def _get_record_path(self, feature_name: str) -> Path:
        clean_name = feature_name.replace("/", "_").replace("\\", "_")
        return self.records_dir / f"{clean_name}.json"

    def get_status(self, feature_name: str) -> dict[str, Any]:
        """Retrieve current lifecycle status and history for a given feature spec.

        Args:
            feature_name: Name or path identifier of the feature.

        Returns:
            Dict containing current_state, history, and feature metadata.
        """
        record_path = self._get_record_path(feature_name)
        if record_path.exists():
            try:
                data: dict[str, Any] = json.loads(record_path.read_text(encoding="utf-8"))
                return data
            except (json.JSONDecodeError, OSError):
                pass

        # Default record for specs without explicit record
        now = datetime.now(timezone.utc).isoformat()
        return {
            "feature_name": feature_name,
            "current_state": LifecycleState.DRAFT.value,
            "created_at": now,
            "updated_at": now,
            "history": [
                {
                    "state": LifecycleState.DRAFT.value,
                    "timestamp": now,
                    "reason": "Initial spec creation",
                }
            ],
        }

    def transition_state(
        self,
        feature_name: str,
        target_state: str | LifecycleState,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Transition feature specification to target lifecycle state.

        Args:
            feature_name: Feature specification name/folder.
            target_state: Desired target state.
            reason: Optional explanation for state change.

        Returns:
            Updated lifecycle record dict.

        Raises:
            InvalidStateTransitionError: If target_state transition is invalid from current state.
        """
        if isinstance(target_state, str):
            try:
                target_enum = LifecycleState(target_state.lower())
            except ValueError as err:
                raise InvalidStateTransitionError(
                    f"Unknown lifecycle state '{target_state}'. "
                    f"Valid states are: {[s.value for s in LifecycleState]}"
                ) from err
        else:
            target_enum = target_state

        current_record = self.get_status(feature_name)
        current_state_str = current_record["current_state"]
        current_enum = LifecycleState(current_state_str)

        if target_enum != current_enum:
            allowed_targets = self.VALID_TRANSITIONS.get(current_enum, set())
            if target_enum not in allowed_targets:
                allowed_str = [s.value for s in allowed_targets]
                raise InvalidStateTransitionError(
                    f"Cannot transition spec '{feature_name}' from state '{current_enum.value}' "
                    f"to '{target_enum.value}'. Allowed transitions: {allowed_str}"
                )

        # Plugin pre-hook dispatch
        self.plugin_registry.dispatch_event(
            "pre_lifecycle_transition",
            feature_name=feature_name,
            current_state=current_enum.value,
            target_state=target_enum.value,
        )

        now = datetime.now(timezone.utc).isoformat()
        current_record["current_state"] = target_enum.value
        current_record["updated_at"] = now
        current_record.setdefault("history", []).append(
            {
                "from_state": current_enum.value,
                "state": target_enum.value,
                "timestamp": now,
                "reason": reason or "State transition executed",
            }
        )

        record_path = self._get_record_path(feature_name)
        record_path.write_text(json.dumps(current_record, indent=2), encoding="utf-8")

        # Plugin event and post-hook dispatch
        self.plugin_registry.dispatch_event(
            "on_lifecycle_transition",
            feature_name=feature_name,
            current_state=current_enum.value,
            target_state=target_enum.value,
        )
        self.plugin_registry.dispatch_event(
            "post_lifecycle_transition",
            feature_name=feature_name,
            current_state=current_enum.value,
            target_state=target_enum.value,
        )

        return current_record

    def list_features(self, state_filter: str | None = None) -> list[dict[str, Any]]:
        """List feature specifications with their lifecycle status.

        Args:
            state_filter: Optional lifecycle state filter string.

        Returns:
            List of feature lifecycle summary records.
        """
        results: list[dict[str, Any]] = []

        # Scan active specs
        if self.specs_dir.exists():
            for child in self.specs_dir.iterdir():
                if child.is_dir() and child.name not in ("archive", "personas"):
                    record = self.get_status(child.name)
                    if state_filter is None or record["current_state"] == state_filter:
                        results.append(record)

        return results
