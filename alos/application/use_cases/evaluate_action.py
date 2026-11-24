"""Use case: evaluate action safety/compliance and log immutable DecisionRecord."""

from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime, timezone

from alos.application.ports.outbound import DecisionLoggerPort as _DLog
from alos.application.ports.outbound import TelemetryPort as _Tel
from alos.domain.models.actions import BaseAction
from alos.domain.models.audit import DecisionRecord
from alos.domain.models.context import ContextPayload
from alos.domain.models.evaluation import EvaluationResult
from alos.domain.services.safety_policy import PolicyRuleRegistry as _Reg


class EvaluateActionUseCase:
    """Application command evaluating domain policies and persisting DecisionRecords."""

    def __init__(
        self,
        registry: _Reg | None = None,
        decision_logger: _DLog | None = None,
        tracer: _Tel | None = None,
    ) -> None:
        self._registry = registry or _Reg.default()
        self._dlog, self._tracer = decision_logger, tracer

    def execute(
        self,
        action: BaseAction,
        context: ContextPayload,
        *,
        trigger: str = "",
        alternatives_considered: list[str] | None = None,
        self_correction_rounds: int = 0,
    ) -> EvaluationResult:
        """Evaluate action against PolicyRuleRegistry and persist DecisionRecord."""
        with self._tracer.span("EvaluateActionUseCase.execute") if self._tracer else nullcontext():
            res, arts = self._registry.evaluate_detailed(action, context)
            if self._dlog is not None:
                p, c = res.preferences_checked, res.corrections_checked
                ok = f"Validated against preferences ({len(p)}) and corrections ({len(c)})"
                rec = DecisionRecord(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    trigger=trigger,
                    action_type=action.action_type,
                    risk_level=res.risk_level,
                    decision="APPROVED" if res.valid else "REJECTED",
                    rationale=ok if res.valid else res.critique,
                    constitution_articles_checked=arts,
                    preferences_checked=p,
                    corrections_checked=c,
                    alternatives_considered=list(alternatives_considered or []),
                    self_correction_rounds=self_correction_rounds,
                )
                self._dlog.log_decision_record(rec)
            return res
