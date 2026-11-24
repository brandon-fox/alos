"""Ring 3 filesystem adapter implementing SpecKitRepositoryPort for LifecycleRecords."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from alos.application.ports.outbound import SpecKitRepositoryPort
from alos.domain.models.speckit import LifecycleRecord, LifecycleState

logger = logging.getLogger(__name__)


class SpecKitFilesystemRepository(SpecKitRepositoryPort):
    """Persists SpecKit LifecycleRecord JSON artifacts under .specify/lifecycle_records/."""

    def __init__(self, root_dir: Path | None = None) -> None:
        self.root_dir = (root_dir or Path.cwd()).resolve()
        self.records_dir = self.root_dir / ".specify" / "lifecycle_records"
        self.records_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        return self.records_dir / f"{name.replace('/', '_').replace(chr(92), '_')}.json"

    def load_record(self, feature_name: str) -> LifecycleRecord:
        """Load persisted LifecycleRecord or synthesize a default DRAFT LifecycleRecord."""
        path = self._path(feature_name)
        if path.exists():
            try:
                return LifecycleRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError, ValidationError) as exc:
                logger.warning("Corrupt SpecKit lifecycle record %s: %s", path, exc)
        now = datetime.now(timezone.utc).isoformat()
        history = [{"state": "draft", "timestamp": now, "reason": "Initial spec creation"}]
        return LifecycleRecord(
            feature_name=feature_name, current_state=LifecycleState.DRAFT, history=history
        )

    def save_record(self, record: LifecycleRecord) -> None:
        """Write frozen LifecycleRecord as formatted UTF-8 JSON."""
        raw = json.dumps(record.model_dump(mode="json"), indent=2)
        self._path(record.feature_name).write_text(raw, encoding="utf-8")
