"""Pure-Python native fallback re-exports for Ring 3 outbound adapters."""

from __future__ import annotations

from alos.native.fallback import (
    FallbackAuditJournalWriter,
    FallbackBM25Indexer,
    FallbackSafetyEvaluator,
)

__all__ = [
    "FallbackAuditJournalWriter",
    "FallbackBM25Indexer",
    "FallbackSafetyEvaluator",
]
