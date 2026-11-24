"""Pure domain models and errors for SpecKit specification lifecycle and archiving.

Ring 1 (Pure Domain): stdlib + pydantic only; zero filesystem I/O.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


class LifecycleRecord(BaseModel):
    """Immutable lifecycle state and transition history for a SpecKit feature."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    feature_name: str
    current_state: LifecycleState = LifecycleState.DRAFT
    created_at: str = Field(default_factory=_utc_now_iso)
    updated_at: str = Field(default_factory=_utc_now_iso)
    history: list[dict[str, Any]] = Field(default_factory=list)


class ArchiveEntry(BaseModel):
    """Immutable archive index entry for an archived SpecKit feature specification."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    feature_name: str
    archived_at: str = Field(default_factory=_utc_now_iso)
    original_path: str
    archive_path: str
    state_at_archive: LifecycleState = LifecycleState.ARCHIVED
