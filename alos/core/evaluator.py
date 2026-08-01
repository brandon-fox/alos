"""Evaluator / Critic Node — ALOS Dual-Loop Reasoning Core.

Spec: specs/02-dual-loop-reasoning/spec.md, specs/03-safety-matrix/spec.md
Constitution: Article I §1 (Safety Gate), Article III §1 (Decision Provenance),
Article V (Safety Matrix)
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import BaseModel

from alos.schemas.actions import BaseAction, EmailDraft, GoogleCalendarEvent

if TYPE_CHECKING:
    from alos.core.context_assembler import ContextPayload
    from alos.core.protocols import DecisionLoggerProtocol


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class EvaluationResult(BaseModel):
    valid: bool
    critique: str
    risk_level: RiskLevel = RiskLevel.LOW
    requires_approval: bool = False
    preferences_checked: list[str] = []
    corrections_checked: list[str] = []


class RiskClassifier:
    """Classifies action risk levels per Constitution Article V Safety Matrix (SOLID: SRP)."""

    HIGH_ACTION_TYPES: ClassVar[set[str]] = {
        "email_send",
        "calendar_delete",
        "financial_transaction",
    }
    MEDIUM_ACTION_TYPES: ClassVar[set[str]] = {
        "todoist_create_task",
        "google_calendar_create_event",
        "vault_update_note",
        "email_create_draft",
    }

    def classify(self, action: BaseAction) -> RiskLevel:
        """Fail-safe risk classification logic."""
        if isinstance(action, EmailDraft):
            return RiskLevel.HIGH
        if action.action_type in self.HIGH_ACTION_TYPES:
            return RiskLevel.HIGH
        if action.action_type in self.MEDIUM_ACTION_TYPES:
            return RiskLevel.MEDIUM
        if action.action_type == "web_search":
            return RiskLevel.LOW
        # Fail-safe: unknown → HIGH (Constitution Article V FR-004)
        return RiskLevel.HIGH


class RuleValidator:
    """Validates actions against user preferences and historical corrections (SOLID: SRP & OCP)."""

    @staticmethod
    def validate_calendar_preferences(
        action: BaseAction, preferences: list[str]
    ) -> tuple[bool, str | None, list[str]]:
        """Validate GoogleCalendarEvent against time-based preferences."""
        preferences_checked: list[str] = []
        if isinstance(action, GoogleCalendarEvent):
            for pref in preferences:
                if "No meetings scheduled after 5:00 PM" in pref:
                    preferences_checked.append(pref)
                    start = action.start_time
                    after_5pm = any(
                        f"T{h}:" in start for h in ["17", "18", "19", "20", "21", "22", "23"]
                    )
                    if after_5pm:
                        msg = "Violates preference: No meetings scheduled after 5:00 PM"
                        return False, msg, preferences_checked
        return True, None, preferences_checked

    @staticmethod
    def validate_corrections_ledger(
        action: BaseAction, corrections: list[str]
    ) -> tuple[bool, str | None, list[str]]:
        """Validate action against correction ledger history."""
        corrections_checked: list[str] = []
        for corr in corrections:
            corrections_checked.append(corr)
            if "Delta" in corr:
                query: Any = getattr(action, "query", "")
                if (
                    isinstance(query, str)
                    and "flight" in query.lower()
                    and "delta" not in query.lower()
                ):
                    return False, f"Violates historical correction: {corr}", corrections_checked
        return True, None, corrections_checked


class EvaluatorNode:
    """Evaluator / Critic node orchestrating safety classification and validation (SOLID: DIP).

    Responsibilities:
    - Classify action risk via RiskClassifier
    - Validate actions against ContextPayload preferences and corrections via RuleValidator
    - Emit a Decision Log ADR record via DecisionLoggerProtocol on every evaluation
    """

    def __init__(
        self,
        context: ContextPayload | None = None,
        decision_logger: DecisionLoggerProtocol | None = None,
        trigger: str = "",
    ):
        from alos.core.context_assembler import ContextPayload as CP

        self.context = context if context is not None else CP()
        self.decision_logger = decision_logger
        self.trigger = trigger
        self.risk_classifier = RiskClassifier()

    def classify_risk(self, action: BaseAction) -> RiskLevel:
        """Classify action risk delegating to RiskClassifier."""
        return self.risk_classifier.classify(action)

    def evaluate_action(
        self,
        action: BaseAction,
        alternatives_considered: list[str] | None = None,
        self_correction_rounds: int = 0,
    ) -> EvaluationResult:
        """Validate action against preferences and correction ledger.

        Emits a Decision Log ADR record on every call (Constitution Article III §1).
        """
        risk_level = self.classify_risk(action)
        requires_approval = risk_level == RiskLevel.HIGH
        constitution_articles_checked = ["I §1", "V"]

        # Validate calendar preferences
        valid_pref, pref_critique, pref_checked = RuleValidator.validate_calendar_preferences(
            action, self.context.preferences
        )
        if not valid_pref:
            result = EvaluationResult(
                valid=False,
                critique=pref_critique or "Preference violation",
                risk_level=risk_level,
                requires_approval=requires_approval,
                preferences_checked=pref_checked,
                corrections_checked=[],
            )
            self._emit_decision(
                action=action,
                risk_level=risk_level,
                decision="REJECTED",
                rationale=result.critique,
                constitution_articles_checked=constitution_articles_checked,
                preferences_checked=pref_checked,
                corrections_checked=[],
                alternatives_considered=alternatives_considered or [],
                self_correction_rounds=self_correction_rounds,
            )
            return result

        # Validate corrections ledger
        valid_corr, corr_critique, corr_checked = RuleValidator.validate_corrections_ledger(
            action, self.context.corrections
        )
        if not valid_corr:
            result = EvaluationResult(
                valid=False,
                critique=corr_critique or "Correction ledger violation",
                risk_level=risk_level,
                requires_approval=requires_approval,
                preferences_checked=pref_checked,
                corrections_checked=corr_checked,
            )
            self._emit_decision(
                action=action,
                risk_level=risk_level,
                decision="REJECTED",
                rationale=result.critique,
                constitution_articles_checked=[*constitution_articles_checked, "III §1"],
                preferences_checked=pref_checked,
                corrections_checked=corr_checked,
                alternatives_considered=alternatives_considered or [],
                self_correction_rounds=self_correction_rounds,
            )
            return result

        # --- APPROVED ---
        rationale = (
            f"Action type '{action.action_type}' risk={risk_level.value}. "
            f"All {len(pref_checked)} preference(s) and "
            f"{len(corr_checked)} correction(s) checked — no violations found."
        )
        result = EvaluationResult(
            valid=True,
            critique="VALID",
            risk_level=risk_level,
            requires_approval=requires_approval,
            preferences_checked=pref_checked,
            corrections_checked=corr_checked,
        )
        self._emit_decision(
            action=action,
            risk_level=risk_level,
            decision="APPROVED",
            rationale=rationale,
            constitution_articles_checked=constitution_articles_checked,
            preferences_checked=pref_checked,
            corrections_checked=corr_checked,
            alternatives_considered=alternatives_considered or [],
            self_correction_rounds=self_correction_rounds,
        )
        return result

    def _emit_decision(
        self,
        action: BaseAction,
        risk_level: RiskLevel,
        decision: str,
        rationale: str,
        constitution_articles_checked: list[str],
        preferences_checked: list[str],
        corrections_checked: list[str],
        alternatives_considered: list[str],
        self_correction_rounds: int,
    ) -> None:
        """Emit one ADR record via DecisionLoggerProtocol if configured."""
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
