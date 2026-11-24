"""Architectural Decision Record (ADR) decision log writer for ALOS.

Spec: specs/010-audit-and-decision-log/spec.md
Spec: specs/035-parallel-testing-and-qa-matrix/spec.md (FR-001, FR-007)
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from typing import TYPE_CHECKING, Any

from alos.logs.telemetry import get_active_span_context
from alos.native import get_journal_writer

if TYPE_CHECKING:
    from alos.core.evaluator import RiskLevel
    from alos.schemas.actions import BaseAction


def _resolve_default_decision_path() -> str:
    env_override = os.environ.get("ALOS_DECISION_LOG_PATH")
    if env_override:
        return env_override
    alos_home = os.environ.get("ALOS_HOME")
    if alos_home:
        return os.path.join(alos_home, "logs", "decision_log.jsonl")
    return os.path.join(os.getcwd(), "logs", "decision_log.jsonl")


class DecisionLogger:
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

    def __init__(self, log_file_path: str | None = None):
        self.log_file_path = log_file_path or _resolve_default_decision_path()
        parent = os.path.dirname(os.path.abspath(self.log_file_path))
        os.makedirs(parent, exist_ok=True)
        self._counter = 0
        self._lock = threading.Lock()
        self._writer = get_journal_writer(self.log_file_path)

    def log_decision(
        self,
        trigger: str,
        action: BaseAction,
        risk_level: RiskLevel,
        decision: str,
        rationale: str,
        constitution_articles_checked: list[str],
        preferences_checked: list[str],
        corrections_checked: list[str],
        alternatives_considered: list[str],
        self_correction_rounds: int,
    ) -> dict[str, Any]:
        """Append one structured ADR Decision Log entry."""
        active_span = get_active_span_context()
        with self._lock:
            self._counter += 1
            record: dict[str, Any] = {
                "timestamp": datetime.now().isoformat(),
                "decision_id": f"D-{self._counter:03d}",
                "trigger": trigger,
                "action_type": action.action_type,
                "risk_level": risk_level.value if hasattr(risk_level, "value") else str(risk_level),
                "decision": decision,
                "rationale": rationale,
                "constitution_articles_checked": constitution_articles_checked,
                "preferences_checked": preferences_checked,
                "corrections_checked": corrections_checked,
                "alternatives_considered": alternatives_considered,
                "self_correction_rounds": self_correction_rounds,
                "trace_id": active_span.trace_id if active_span else None,
                "span_id": active_span.span_id if active_span else None,
            }
        self._writer.append_record(json.dumps(record))
        return record
