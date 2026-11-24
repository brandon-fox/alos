"""Use case: formulate candidate BaseAction drafts via domain strategy registry."""

from __future__ import annotations

from contextlib import nullcontext

from alos.application.ports.outbound import TelemetryPort
from alos.domain.models.actions import BaseAction
from alos.domain.models.context import ContextPayload as _Ctx
from alos.domain.services.draft_builder import ActionDraftStrategyRegistry as _Reg


class PlanActionUseCase:
    """Application command orchestrating ActionDraftStrategyRegistry for draft planning."""

    def __init__(self, registry: _Reg | None = None, tracer: TelemetryPort | None = None) -> None:
        self._registry, self._tracer = registry or _Reg.default(), tracer

    def execute(
        self, user_query: str, context: _Ctx | None = None, critique_feedback: str | None = None
    ) -> BaseAction:
        """Generate an immutable BaseAction draft incorporating optional critique."""
        _ = context
        with self._tracer.span("PlanActionUseCase.execute") if self._tracer else nullcontext():
            return self._registry.build_draft(user_query, critique_feedback)
