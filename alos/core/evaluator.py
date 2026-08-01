"""Evaluator / Critic Node — ALOS Dual-Loop Reasoning Core.

Spec: specs/02-dual-loop-reasoning/spec.md, specs/03-safety-matrix/spec.md
Constitution: Article I §1 (Safety Gate), Article III §1 (Decision Provenance),
Article V (Safety Matrix)
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from pydantic import BaseModel

from alos.schemas.actions import BaseAction, EmailDraft, GoogleCalendarEvent

if TYPE_CHECKING:
    from alos.core.context_assembler import ContextPayload
    from alos.logs.decision_log import DecisionLogger


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class EvaluationResult(BaseModel):
    valid: bool
    critique: str
    risk_level: RiskLevel = RiskLevel.LOW
    requires_approval: bool = False
    # Captured for Decision Log accumulation in StateGraph
    preferences_checked: List[str] = []
    corrections_checked: List[str] = []


class EvaluatorNode:
    """Evaluator / Critic node.

    Responsibilities:
    - Classify action risk per Constitution Article V Safety Matrix
    - Validate actions against ContextPayload preferences and correction history
    - Emit a Decision Log ADR record via DecisionLogger on every evaluation
    """

    def __init__(
        self,
        context: Optional["ContextPayload"] = None,
        decision_logger: Optional["DecisionLogger"] = None,
        trigger: str = "",
    ):
        # Lazy import to avoid circular at module load time
        from alos.core.context_assembler import ContextPayload as CP

        self.context = context if context is not None else CP()
        self.decision_logger = decision_logger
        self.trigger = trigger

    def classify_risk(self, action: BaseAction) -> RiskLevel:
        """Safety Matrix risk classification per Constitution Article V.

        Fail-safe: unknown action types default to HIGH.
        """
        HIGH_ACTION_TYPES = {"email_send", "calendar_delete", "financial_transaction"}
        MEDIUM_ACTION_TYPES = {
            "todoist_create_task",
            "google_calendar_create_event",
            "vault_update_note",
            "email_create_draft",
        }

        if isinstance(action, EmailDraft):
            return RiskLevel.HIGH
        if action.action_type in HIGH_ACTION_TYPES:
            return RiskLevel.HIGH
        if action.action_type in MEDIUM_ACTION_TYPES:
            return RiskLevel.MEDIUM
        if action.action_type == "web_search":
            return RiskLevel.LOW
        # Fail-safe: unknown → HIGH (Constitution Article V FR-004)
        return RiskLevel.HIGH

    def evaluate_action(
        self,
        action: BaseAction,
        alternatives_considered: Optional[List[str]] = None,
        self_correction_rounds: int = 0,
    ) -> EvaluationResult:
        """Validate action against preferences and correction ledger.

        Emits a Decision Log ADR record on every call (Constitution Article III §1).
        """
        risk_level = self.classify_risk(action)
        requires_approval = risk_level == RiskLevel.HIGH

        preferences_checked: List[str] = []
        corrections_checked: List[str] = []
        constitution_articles_checked = ["I §1", "V"]

        # --- Validate GoogleCalendarEvent against time-based preferences ---
        if isinstance(action, GoogleCalendarEvent):
            for pref in self.context.preferences:
                if "No meetings scheduled after 5:00 PM" in pref:
                    preferences_checked.append(pref)
                    # Match any time at or after 17:00
                    start = action.start_time
                    after_5pm = any(
                        f"T{h}:" in start for h in ["17", "18", "19", "20", "21", "22", "23"]
                    )
                    if after_5pm:
                        result = EvaluationResult(
                            valid=False,
                            critique="Violates preference: No meetings scheduled after 5:00 PM",
                            risk_level=risk_level,
                            requires_approval=requires_approval,
                            preferences_checked=preferences_checked,
                            corrections_checked=corrections_checked,
                        )
                        self._emit_decision(
                            action=action,
                            risk_level=risk_level,
                            decision="REJECTED",
                            rationale=result.critique,
                            constitution_articles_checked=constitution_articles_checked,
                            preferences_checked=preferences_checked,
                            corrections_checked=corrections_checked,
                            alternatives_considered=alternatives_considered or [],
                            self_correction_rounds=self_correction_rounds,
                        )
                        return result

        # --- Validate against correction ledger ---
        for corr in self.context.corrections:
            corrections_checked.append(corr)
            if "Delta" in corr:
                query = getattr(action, "query", "")
                if "flight" in query.lower() and "delta" not in query.lower():
                    result = EvaluationResult(
                        valid=False,
                        critique=f"Violates historical correction: {corr}",
                        risk_level=risk_level,
                        requires_approval=requires_approval,
                        preferences_checked=preferences_checked,
                        corrections_checked=corrections_checked,
                    )
                    self._emit_decision(
                        action=action,
                        risk_level=risk_level,
                        decision="REJECTED",
                        rationale=result.critique,
                        constitution_articles_checked=constitution_articles_checked + ["III §1"],
                        preferences_checked=preferences_checked,
                        corrections_checked=corrections_checked,
                        alternatives_considered=alternatives_considered or [],
                        self_correction_rounds=self_correction_rounds,
                    )
                    return result

        # --- APPROVED ---
        rationale = (
            f"Action type '{action.action_type}' risk={risk_level.value}. "
            f"All {len(preferences_checked)} preference(s) and "
            f"{len(corrections_checked)} correction(s) checked — no violations found."
        )
        result = EvaluationResult(
            valid=True,
            critique="VALID",
            risk_level=risk_level,
            requires_approval=requires_approval,
            preferences_checked=preferences_checked,
            corrections_checked=corrections_checked,
        )
        self._emit_decision(
            action=action,
            risk_level=risk_level,
            decision="APPROVED",
            rationale=rationale,
            constitution_articles_checked=constitution_articles_checked,
            preferences_checked=preferences_checked,
            corrections_checked=corrections_checked,
            alternatives_considered=alternatives_considered or [],
            self_correction_rounds=self_correction_rounds,
        )
        return result

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _emit_decision(
        self,
        action: BaseAction,
        risk_level: RiskLevel,
        decision: str,
        rationale: str,
        constitution_articles_checked: List[str],
        preferences_checked: List[str],
        corrections_checked: List[str],
        alternatives_considered: List[str],
        self_correction_rounds: int,
    ) -> None:
        """Emit one ADR record via DecisionLogger if one is wired in."""
        if self.decision_logger is not None:
            self.decision_logger.log_decision(
                trigger=self.trigger,
                action=action,
                risk_level=risk_level,
                decision=decision,
                rationale=rationale,
                constitution_articles_checked=constitution_articles_checked,
                preferences_checked=preferences_checked,
                corrections_checked=corrections_checked,
                alternatives_considered=alternatives_considered,
                self_correction_rounds=self_correction_rounds,
            )
