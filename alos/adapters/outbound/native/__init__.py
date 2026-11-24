"""Outbound native PyO3 and pure-Python fallback adapters (Spec 036, ADR-0024)."""

from __future__ import annotations

from alos.adapters.outbound.native.bridge import (
    NativeSafetyAcceleratorAdapter,
    get_bm25_indexer,
    get_journal_writer,
    get_safety_evaluator,
)
from alos.adapters.outbound.native.fallback import (
    FallbackAuditJournalWriter,
    FallbackBM25Indexer,
    FallbackSafetyEvaluator,
)
from alos.native import HAS_NATIVE_EXTENSION

__all__ = [
    "HAS_NATIVE_EXTENSION",
    "FallbackAuditJournalWriter",
    "FallbackBM25Indexer",
    "FallbackSafetyEvaluator",
    "NativeSafetyAcceleratorAdapter",
    "get_bm25_indexer",
    "get_journal_writer",
    "get_safety_evaluator",
]
