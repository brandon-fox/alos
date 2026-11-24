"""Hexagonal Ring 3 adapter bridge wrapping PyO3 native and pure-Python accelerators."""

from __future__ import annotations

from typing import Any

from alos.domain.models.evaluation import RiskLevel
from alos.native.bridge import (
    get_bm25_indexer,
    get_journal_writer,
    get_safety_evaluator,
)


class NativeSafetyAcceleratorAdapter:
    """Driven adapter wrapping FastSafetyEvaluator or FallbackSafetyEvaluator."""

    def __init__(self, evaluator: Any | None = None) -> None:
        self._evaluator = evaluator if evaluator is not None else get_safety_evaluator()

    def classify_risk(self, action_type: str) -> RiskLevel:
        """Classify action risk into canonical domain RiskLevel."""
        return RiskLevel(self._evaluator.classify_risk(action_type))

    def validate_calendar_preferences(
        self, action_type: str, start_time: str, preferences: list[str]
    ) -> dict[str, Any]:
        """Validate calendar scheduling parameters against preference rules."""
        res: dict[str, Any] = dict(
            self._evaluator.validate_calendar_preferences(action_type, start_time, preferences)
        )
        return res

    def validate_corrections(self, query: str, corrections: list[str]) -> dict[str, Any]:
        """Validate user query against historical correction ledger entries."""
        res: dict[str, Any] = dict(self._evaluator.validate_corrections(query, corrections))
        return res


__all__ = [
    "NativeSafetyAcceleratorAdapter",
    "get_bm25_indexer",
    "get_journal_writer",
    "get_safety_evaluator",
]
