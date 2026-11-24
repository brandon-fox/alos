"""Ring 1 pure domain safety policies and OCP rule registry (ADR-0023, FR-3605/3606)."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar, Protocol, runtime_checkable

import alos.domain.models.actions as act
from alos.domain.models.context import ContextPayload
from alos.domain.models.evaluation import EvaluationResult, RiskLevel

_GCE, _TTC = act.GoogleCalendarEvent, act.TodoistTaskCreate


class RiskClassificationPolicy:
    """Pure-domain Safety Matrix risk classifier (Constitution Article V, SOLID: SRP)."""

    TIER_MAP: ClassVar[dict[str, RiskLevel]] = {
        "web_search": RiskLevel.LOW,
        "todoist_create_task": RiskLevel.MEDIUM,
        "google_calendar_create_event": RiskLevel.MEDIUM,
        "vault_update_note": RiskLevel.MEDIUM,
    }

    def classify(self, action: act.BaseAction | str) -> RiskLevel:
        """Classify an action or action_type into LOW, MEDIUM, or HIGH (fail-safe HIGH)."""
        if isinstance(action, act.EmailDraft | act.EmailSend):
            return RiskLevel.HIGH
        atype = action if isinstance(action, str) else action.action_type
        return self.TIER_MAP.get(atype, RiskLevel.HIGH)


@dataclass(frozen=True)
class RuleOutcome:
    """Immutable single-specification evaluation outcome returned by a PolicyRule."""

    passed: bool
    critique: str | None = None
    checked_items: list[str] = field(default_factory=list)
    is_correction: bool = False
    constitution_article: str | None = None


@runtime_checkable
class PolicyRule(Protocol):
    """Specification protocol for composable safety and preference rules (SOLID: OCP)."""

    def evaluate(self, action: act.BaseAction, context: ContextPayload) -> RuleOutcome:
        """Evaluate an action against domain context rules and return a RuleOutcome."""
        ...


RuleFn = Callable[[act.BaseAction, ContextPayload], RuleOutcome]


def _rule_5pm(a: act.BaseAction, ctx: ContextPayload) -> RuleOutcome:
    chk = [p for p in ctx.preferences if "No meetings scheduled after 5:00 PM" in p]
    if chk and isinstance(a, _GCE) and any(f"T{h}:" in a.start_time for h in range(17, 24)):
        return RuleOutcome(False, "Violates preference: No meetings scheduled after 5:00 PM", chk)
    return RuleOutcome(True, checked_items=chk)


def _rule_fri(a: act.BaseAction, ctx: ContextPayload) -> RuleOutcome:
    chk = [p for p in ctx.preferences if "friday" in p.lower() and ("3:00" in p or "15:00" in p)]
    if chk and isinstance(a, _GCE):
        with suppress(ValueError):
            dt = datetime.fromisoformat(a.start_time)
            if dt.weekday() == 4 and dt.hour >= 15:
                return RuleOutcome(False, f"Violates preference: {chk[0]}", chk)
    return RuleOutcome(True, checked_items=chk)


def _rule_todoist(a: act.BaseAction, ctx: ContextPayload) -> RuleOutcome:
    chk = [p for p in ctx.preferences if "@high" in p.lower()]
    if not chk or not isinstance(a, _TTC) or a.priority == 1:
        return RuleOutcome(True, checked_items=chk)
    if "@high" in a.title.lower() or "high" in [x.lower() for x in a.labels]:
        return RuleOutcome(False, f"Violates preference: {chk[0]}", chk)
    return RuleOutcome(True, checked_items=chk)


def _rule_delta(a: act.BaseAction, ctx: ContextPayload) -> RuleOutcome:
    chk, qlow = list(ctx.corrections), str(getattr(a, "query", "")).lower()
    for i, c in enumerate(chk):
        if "Delta" in c and "flight" in qlow and "delta" not in qlow:
            msg = f"Violates historical correction: {c}"
            return RuleOutcome(False, msg, chk[: i + 1], True, "III §1")
    return RuleOutcome(True, checked_items=chk, is_correction=True)


class PolicyRuleRegistry:
    """Extensible Open-Closed registry orchestrating RiskClassificationPolicy and PolicyRules."""

    def __init__(self, rules: list[PolicyRule | RuleFn] | None = None) -> None:
        self._rules: list[PolicyRule | RuleFn] = list(rules or [])

    def register(self, rule: PolicyRule | RuleFn) -> None:
        """Register an additional PolicyRule without modifying core evaluator code (OCP)."""
        self._rules.append(rule)

    @classmethod
    def default(cls) -> PolicyRuleRegistry:
        """Construct registry populated with ALOS built-in preference and correction rules."""
        return cls([_rule_5pm, _rule_fri, _rule_todoist, _rule_delta])

    def evaluate_detailed(
        self, a: act.BaseAction, ctx: ContextPayload
    ) -> tuple[EvaluationResult, list[str]]:
        """Evaluate action against all rules, returning EvaluationResult and checked articles."""
        risk = RiskClassificationPolicy().classify(a)
        arts, valid, critique = ["I §1", "V"], True, "VALID"
        buckets: dict[bool, list[str]] = {False: [], True: []}
        for r in self._rules:
            out = r.evaluate(a, ctx) if isinstance(r, PolicyRule) else r(a, ctx)
            buckets[out.is_correction].extend(out.checked_items)
            if not out.passed:
                if out.constitution_article and out.constitution_article not in arts:
                    arts.append(out.constitution_article)
                valid, critique = False, out.critique or "Policy rule violation"
                break
        res = EvaluationResult(
            valid=valid,
            critique=critique,
            risk_level=risk,
            requires_approval=risk == RiskLevel.HIGH,
            preferences_checked=buckets[False],
            corrections_checked=buckets[True],
        )
        return res, arts

    def evaluate(self, action: act.BaseAction, context: ContextPayload) -> EvaluationResult:
        """Evaluate action against registered policies and return immutable EvaluationResult."""
        return self.evaluate_detailed(action, context)[0]
