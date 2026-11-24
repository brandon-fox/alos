"""Strangler-Fig facade delegating SpecKit archiving and restoration to Ring 2."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from alos.application.use_cases.speckit_lifecycle import SpecKitArchiveUseCase
from alos.integrations.speckit.lifecycle import SpecKitLifecycleManager
from alos.integrations.speckit.plugins import SpecKitPluginRegistry


class SpecKitArchiver:
    """Backwards-compatible facade delegating archiving/restoration to SpecKitArchiveUseCase."""

    def __init__(
        self,
        root_dir: Path | None = None,
        plugin_registry: SpecKitPluginRegistry | None = None,
    ) -> None:
        self.root_dir = root_dir.resolve() if root_dir else Path.cwd().resolve()
        self.specs_dir = self.root_dir / "specs"
        self.plugin_registry = (
            plugin_registry if plugin_registry is not None else SpecKitPluginRegistry.get_instance()
        )
        self.lifecycle_manager = SpecKitLifecycleManager(
            root_dir=self.root_dir, plugin_registry=self.plugin_registry
        )
        self._use_case = SpecKitArchiveUseCase(
            lifecycle=self.lifecycle_manager._use_case,
            specs_dir=self.specs_dir,
            hooks=self.plugin_registry,
        )
        self.archive_dir = self._use_case.archive_dir
        self.archive_index_path = self._use_case.archive_index_path

    def archive_feature(self, feature_name: str) -> dict[str, Any]:
        """Archive an active feature specification directory."""
        return self._use_case.archive_feature(feature_name)

    def restore_feature(self, feature_name: str) -> dict[str, Any]:
        """Restore an archived feature specification directory back to specs/."""
        return self._use_case.restore_feature(feature_name)

    def list_archived_features(self) -> list[dict[str, Any]]:
        """List archived feature specifications from archive index."""
        return self._use_case.list_archived_features()
