"""Hexagonal Ring 2 inbound (driving) CQRS handler protocols."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from alos.domain.models.actions import BaseAction as _Act
from alos.domain.models.context import ContextPayload as _Ctx
from alos.domain.models.evaluation import EvaluationResult as _Eval


@runtime_checkable
class AssembleContextHandler(Protocol):
    """Inbound query port assembling immutable ContextPayload from vault and memory."""

    def execute(self, user_query: str, *, top_k: int = 5) -> _Ctx:
        """Assemble context for user_query."""


@runtime_checkable
class PlanActionHandler(Protocol):
    """Inbound command port generating a candidate BaseAction draft."""

    def execute(
        self, user_query: str, context: _Ctx | None = None, critique_feedback: str | None = None
    ) -> _Act:
        """Formulate candidate draft action."""


@runtime_checkable
class EvaluateActionHandler(Protocol):
    """Inbound command port validating actions against Safety Matrix and logging decisions."""

    def execute(
        self,
        action: _Act,
        context: _Ctx,
        *,
        trigger: str = "",
        alternatives_considered: list[str] | None = None,
        self_correction_rounds: int = 0,
    ) -> _Eval:
        """Evaluate action safety and compliance."""
