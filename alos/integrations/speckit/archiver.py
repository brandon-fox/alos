"""SpecKit archiver for archiving and restoring completed feature specifications."""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from alos.integrations.speckit.lifecycle import LifecycleState, SpecKitLifecycleManager
from alos.integrations.speckit.plugins import SpecKitPluginRegistry


class SpecKitArchiver:
    """Archiving and restoration engine for SpecKit feature specifications."""

    def __init__(self, root_dir: Optional[Path] = None) -> None:
        self.root_dir = root_dir.resolve() if root_dir else Path.cwd().resolve()
        self.specs_dir = self.root_dir / "specs"
        self.archive_dir = self.specs_dir / "archive"
        self.archive_index_path = self.archive_dir / "archive-index.json"
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self.lifecycle_manager = SpecKitLifecycleManager(root_dir=self.root_dir)
        self.plugin_registry = SpecKitPluginRegistry.get_instance()

    def _read_archive_index(self) -> Dict[str, Dict[str, Any]]:
        if self.archive_index_path.exists():
            try:
                data: Dict[str, Dict[str, Any]] = json.loads(
                    self.archive_index_path.read_text(encoding="utf-8")
                )
                return data
            except Exception:
                pass
        return {}

    def _write_archive_index(self, index_data: Dict[str, Dict[str, Any]]) -> None:
        self.archive_index_path.write_text(
            json.dumps(index_data, indent=2), encoding="utf-8"
        )

    def archive_feature(self, feature_name: str) -> Dict[str, Any]:
        """Archive an active feature specification directory.

        Args:
            feature_name: Name of the feature folder in specs/.

        Returns:
            Dict containing archived feature metadata.

        Raises:
            FileNotFoundError: If feature directory does not exist under specs/.
        """
        source_dir = self.specs_dir / feature_name
        if not source_dir.exists() or not source_dir.is_dir():
            raise FileNotFoundError(
                f"Feature specification directory '{source_dir}' not found."
            )

        dest_dir = self.archive_dir / feature_name
        if dest_dir.exists():
            shutil.rmtree(dest_dir)

        # Dispatch pre_archive plugin hook
        self.plugin_registry.dispatch_event(
            "pre_archive", feature_name=feature_name, source_path=str(source_dir)
        )

        # Ensure lifecycle state is updated to archived
        status = self.lifecycle_manager.get_status(feature_name)
        curr_state = status.get("current_state")
        if curr_state != LifecycleState.ARCHIVED.value:
            # If not in completed/deprecated, transition to completed first if draft/in_progress
            if curr_state in [LifecycleState.DRAFT.value, LifecycleState.IN_PROGRESS.value]:
                self.lifecycle_manager.transition_state(
                    feature_name, LifecycleState.APPROVED.value, reason="Pre-archive transition"
                )
                self.lifecycle_manager.transition_state(
                    feature_name, LifecycleState.COMPLETED.value, reason="Pre-archive transition"
                )
            self.lifecycle_manager.transition_state(
                feature_name, LifecycleState.ARCHIVED.value, reason="Archived feature spec"
            )

        # Move feature directory to specs/archive/<feature_name>
        shutil.move(str(source_dir), str(dest_dir))

        now = datetime.now(timezone.utc).isoformat()
        archive_info = {
            "feature_name": feature_name,
            "archived_at": now,
            "original_path": str(source_dir),
            "archive_path": str(dest_dir),
            "state_at_archive": LifecycleState.ARCHIVED.value,
        }

        # Update index
        index = self._read_archive_index()
        index[feature_name] = archive_info
        self._write_archive_index(index)

        # Dispatch plugin hooks
        self.plugin_registry.dispatch_event(
            "on_archive", feature_name=feature_name, archive_info=archive_info
        )
        self.plugin_registry.dispatch_event(
            "post_archive", feature_name=feature_name, archive_info=archive_info
        )

        return archive_info

    def restore_feature(self, feature_name: str) -> Dict[str, Any]:
        """Restore an archived feature specification directory back to specs/.

        Args:
            feature_name: Name of the feature folder in specs/archive/.

        Returns:
            Dict containing restored feature metadata.

        Raises:
            FileNotFoundError: If archived feature directory does not exist.
        """
        source_dir = self.archive_dir / feature_name
        if not source_dir.exists() or not source_dir.is_dir():
            raise FileNotFoundError(
                f"Archived feature specification directory '{source_dir}' not found."
            )

        dest_dir = self.specs_dir / feature_name

        # Dispatch pre_restore plugin hook
        self.plugin_registry.dispatch_event(
            "pre_restore", feature_name=feature_name, archive_path=str(source_dir)
        )

        shutil.move(str(source_dir), str(dest_dir))

        # Transition lifecycle state back from archived to draft
        self.lifecycle_manager.transition_state(
            feature_name, LifecycleState.DRAFT.value, reason="Restored from archive"
        )

        # Remove from index
        index = self._read_archive_index()
        if feature_name in index:
            del index[feature_name]
            self._write_archive_index(index)

        now = datetime.now(timezone.utc).isoformat()
        restore_info = {
            "feature_name": feature_name,
            "restored_at": now,
            "restored_path": str(dest_dir),
        }

        # Dispatch post_restore plugin hook
        self.plugin_registry.dispatch_event(
            "post_restore", feature_name=feature_name, restore_info=restore_info
        )

        return restore_info

    def list_archived_features(self) -> List[Dict[str, Any]]:
        """List archived feature specifications from archive index."""
        index = self._read_archive_index()
        return list(index.values())
