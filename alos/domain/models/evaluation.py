"""Pure domain models for Safety Matrix risk tiers and evaluation outcomes.

Ring 1 (Pure Domain): stdlib + pydantic only (Constitution Articles I §1, V).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class RiskLevel(str, Enum):
    """Enumeration of Constitution Article V Safety Matrix risk classification tiers."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class EvaluationResult(BaseModel):
    """Immutable outcome of evaluating a planned action against safety and vault rules."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    valid: bool
    critique: str
    risk_level: RiskLevel = RiskLevel.LOW
    requires_approval: bool = False
    preferences_checked: list[str] = Field(default_factory=list)
    corrections_checked: list[str] = Field(default_factory=list)
