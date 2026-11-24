"""Ring 2 pure application use case for SpecKit specification lifecycle management."""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from alos.application.ports.outbound import SpecKitRepositoryPort
from alos.domain.models.speckit import ArchiveEntry, LifecycleState
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


class SpecKitArchiveUseCase:
    """Ring 2 use case archiving and restoring SpecKit feature directories."""

    def __init__(
        self,
        lifecycle: SpecKitLifecycleUseCase,
        specs_dir: Path,
        hooks: LifecycleHookDispatcher | None = None,
    ) -> None:
        self.lifecycle = lifecycle
        self.specs_dir = specs_dir
        self.archive_dir = self.specs_dir / "archive"
        self.archive_index_path = self.archive_dir / "archive-index.json"
        self.hooks = hooks
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    def _emit(self, event_name: str, **kwargs: Any) -> None:
        if self.hooks is not None:
            self.hooks.dispatch_event(event_name, **kwargs)

    def _read_index(self) -> dict[str, _Map]:
        if self.archive_index_path.exists():
            try:
                raw: dict[str, _Map] = json.loads(self.archive_index_path.read_text("utf-8"))
                return raw
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _write_index(self, data: dict[str, _Map]) -> None:
        self.archive_index_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def archive_feature(self, feature_name: str) -> _Map:
        """Transition feature to ARCHIVED, relocate directory, and record ArchiveEntry."""
        src, dst = self.specs_dir / feature_name, self.archive_dir / feature_name
        if not src.exists() or not src.is_dir():
            raise FileNotFoundError(f"Feature specification directory '{src}' not found.")
        if dst.exists():
            shutil.rmtree(dst)
        self._emit("pre_archive", feature_name=feature_name, source_path=str(src))
        curr = self.lifecycle.get_status(feature_name).get("current_state")
        if curr != LifecycleState.ARCHIVED.value:
            if curr in (LifecycleState.DRAFT.value, LifecycleState.IN_PROGRESS.value):
                self.lifecycle.transition_state(
                    feature_name, LifecycleState.APPROVED, reason="Pre-archive transition"
                )
                self.lifecycle.transition_state(
                    feature_name, LifecycleState.COMPLETED, reason="Pre-archive transition"
                )
            self.lifecycle.transition_state(
                feature_name, LifecycleState.ARCHIVED, reason="Archived feature spec"
            )
        shutil.move(str(src), str(dst))
        entry = ArchiveEntry(
            original_path=str(src), archive_path=str(dst), feature_name=feature_name
        )
        info = entry.model_dump(mode="json")
        index = self._read_index()
        index[feature_name] = info
        self._write_index(index)
        self._emit("on_archive", feature_name=feature_name, archive_info=info)
        self._emit("post_archive", feature_name=feature_name, archive_info=info)
        return info

    def restore_feature(self, feature_name: str) -> _Map:
        """Restore an archived feature directory back to specs/ and transition to DRAFT."""
        src, dst = self.archive_dir / feature_name, self.specs_dir / feature_name
        if not src.exists() or not src.is_dir():
            raise FileNotFoundError(f"Archived feature specification directory '{src}' not found.")
        self._emit("pre_restore", feature_name=feature_name, archive_path=str(src))
        shutil.move(str(src), str(dst))
        self.lifecycle.transition_state(
            feature_name, LifecycleState.DRAFT, reason="Restored from archive"
        )
        index = self._read_index()
        if feature_name in index:
            del index[feature_name]
            self._write_index(index)
        info = {
            "feature_name": feature_name,
            "restored_at": datetime.now(timezone.utc).isoformat(),
            "restored_path": str(dst),
        }
        self._emit("post_restore", feature_name=feature_name, restore_info=info)
        return info

    def list_archived_features(self) -> list[_Map]:
        """List archived feature specifications from the archive index."""
        return list(self._read_index().values())
