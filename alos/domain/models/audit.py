"""Pure domain provenance models for decision ADRs and append-only audit events.

Ring 1 (Pure Domain): stdlib + pydantic + alos.domain only (Constitution Article III §1-§2).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from alos.domain.models.evaluation import RiskLevel


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DecisionRecord(BaseModel):
    """Immutable Constitutional Article III decision provenance record."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    timestamp: str = Field(default_factory=_utc_now_iso)
    decision_id: str = "D-001"
    trigger: str = ""
    action_type: str
    risk_level: RiskLevel
    decision: Literal["APPROVED", "REJECTED"]
    rationale: str
    constitution_articles_checked: list[str] = Field(default_factory=list)
    preferences_checked: list[str] = Field(default_factory=list)
    corrections_checked: list[str] = Field(default_factory=list)
    alternatives_considered: list[str] = Field(default_factory=list)
    self_correction_rounds: int = Field(default=0, ge=0)
    trace_id: str | None = None
    span_id: str | None = None


class AuditEvent(BaseModel):
    """Immutable append-only system audit journal event (Constitution Article III §2)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    timestamp: str = Field(default_factory=_utc_now_iso)
    step: str
    status: str
    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None
    span_id: str | None = None
