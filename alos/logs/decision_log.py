"""Architectural Decision Record (ADR) decision log writer for ALOS.

Spec: specs/010-audit-and-decision-log/spec.md
Spec: specs/035-parallel-testing-and-qa-matrix/spec.md (FR-001, FR-007)
"""

from __future__ import annotations

from alos.adapters.outbound.audit.jsonl_decision_log import JsonlDecisionLogAdapter


class DecisionLogger(JsonlDecisionLogAdapter):
    """Runtime Decision Log (ADR) writer.

    Implements Constitution Article III §1: Decision Provenance.
    Every evaluate_action() call produces one append-only JSONL record in
    logs/decision_log.jsonl capturing the full rationale for APPROVED/REJECTED decisions.

    Record schema (12 required fields per specs/010-audit-and-decision-log/spec.md FR-006):
        timestamp                   : ISO-8601
        decision_id                 : "D-NNN" (session-scoped counter)
        trigger                     : original user query
        action_type                 : action.action_type
        risk_level                  : LOW | MEDIUM | HIGH
        decision                    : APPROVED | REJECTED
        rationale                   : human-readable explanation
        constitution_articles_checked : list of article references
        preferences_checked         : list of preference strings evaluated
        corrections_checked         : list of correction strings evaluated
        alternatives_considered     : list of rejected alternatives with reason
        self_correction_rounds      : integer count of prior rejection rounds
    """
