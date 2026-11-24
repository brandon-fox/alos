"""RED-first unit tests for Ring 1 pure domain policies, draft registry, and lifecycle FSM."""

from __future__ import annotations

import pytest

import alos.domain.models.actions as act
import alos.domain.services as svc
from alos.domain.models.context import ContextPayload
from alos.domain.models.evaluation import RiskLevel
from alos.domain.models.speckit import InvalidStateTransitionError, LifecycleRecord, LifecycleState


def _ev(start: str) -> act.GoogleCalendarEvent:
    return act.GoogleCalendarEvent(title="S", start_time=start, end_time="18")


def test_risk_and_policy_rule_registry() -> None:
    """RiskClassificationPolicy and PolicyRuleRegistry enforce tiers, built-ins, and OCP."""
    p, reg = svc.RiskClassificationPolicy(), svc.PolicyRuleRegistry.default()
    ttc, vnu, es = act.TodoistTaskCreate, act.VaultNoteUpdate, act.EmailSend
    m = {"to_email": "a@b.c", "subject": "S", "body": "B"}
    assert p.classify(act.WebSearchQuery(query="q")) == RiskLevel.LOW
    assert p.classify(ttc(title="B")) == p.classify(_ev("1")) == RiskLevel.MEDIUM
    assert p.classify(vnu(filename="n", content="o")) == RiskLevel.MEDIUM
    assert p.classify(act.EmailDraft.model_validate(m)) == RiskLevel.HIGH
    assert p.classify(es.model_validate(m)) == RiskLevel.HIGH
    assert p.classify(act.BaseAction(action_type="x", description="x")) == RiskLevel.HIGH
    p12 = ["No meetings scheduled after 5:00 PM", "No meetings on Friday after 3:00 PM"]
    ctx = ContextPayload(
        preferences=[*p12, "Tasks tagged @high must have priority 1"],
        corrections=["Never book flights without checking Delta options first"],
    )
    assert "5:00 PM" in reg.evaluate(_ev("2026-08-03T17:30:00"), ctx).critique
    assert not reg.evaluate(_ev("2026-08-07T15:30:00"), ctx).valid
    assert reg.evaluate(_ev("2026-08-03T10:00:00"), ctx).valid
    assert reg.evaluate(_ev("bad"), ctx).valid
    assert not reg.evaluate(ttc(title="Fix @high", priority=3), ctx).valid
    assert reg.evaluate(ttc(title="N", priority=3), ctx).valid
    assert reg.evaluate(ttc(title="Fix @high", priority=1), ctx).valid
    rc, arts = reg.evaluate_detailed(act.WebSearchQuery(query="Book United flight"), ctx)
    assert not rc.valid and "Violates historical correction:" in rc.critique and "III §1" in arts

    class _NoSpam:
        def evaluate(self, a: act.BaseAction, _c: ContextPayload) -> svc.RuleOutcome:
            bad = isinstance(a, es) and "spam" in a.subject.lower()
            return svc.RuleOutcome(passed=not bad, critique="Blocked spam" if bad else None)

    reg.register(_NoSpam())
    blk = reg.evaluate(es(to_email="a@b.c", subject="SPAM", body="x"), ctx)
    assert not blk.valid and blk.requires_approval and blk.critique == "Blocked spam"


def test_draft_registry_and_lifecycle_fsm() -> None:
    """ActionDraftStrategyRegistry and SpecKitLifecycleFSM handle dispatch, OCP, and jumps."""
    reg, fsm = svc.ActionDraftStrategyRegistry.default(), svc.SpecKitLifecycleFSM
    fn = svc.ActionDraftBuilder.build_task_action
    assert "17:30:00" in str(reg.build_draft("Schedule meeting Team Sync"))
    assert "14:00:00" in str(reg.build_draft("Schedule meeting Team Sync", "5:00 PM"))
    assert isinstance(reg.build_draft("Schedule lunch"), act.GoogleCalendarEvent)
    assert isinstance(reg.build_draft("Create task review"), act.TodoistTaskCreate)
    assert isinstance(reg.build_draft("Send email update"), act.EmailSend)
    assert isinstance(reg.build_draft("Search local RAG"), act.WebSearchQuery)
    reg.register(svc.KeywordDraftStrategy(("meeting note",), fn))
    reg.register(svc.KeywordDraftStrategy(("fallback",), fn), prepend=False)
    assert isinstance(reg.build_draft("Schedule meeting note"), act.TodoistTaskCreate)
    assert isinstance(reg.build_draft("fallback"), act.TodoistTaskCreate)
    rec = LifecycleRecord(feature_name="036-test")
    nxt = fsm.apply_transition(rec, "in_progress", reason="Start")
    assert nxt.current_state == LifecycleState.IN_PROGRESS and len(nxt.history) == 1
    assert fsm.parse_state(LifecycleState.DRAFT) == LifecycleState.DRAFT
    for bad in (LifecycleState.ARCHIVED, "unknown_state"):
        with pytest.raises(InvalidStateTransitionError):
            fsm.apply_transition(rec, bad)
