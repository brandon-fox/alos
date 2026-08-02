"""ALOS Native Bridge Wrapper Interface.

Spec: specs/003-rust-core-architectural-refactor/spec.md (FR-009)
"""

from __future__ import annotations

from typing import Any

from alos.native.fallback import (
    FallbackAuditJournalWriter,
    FallbackBM25Indexer,
    FallbackSafetyEvaluator,
)

# Attempt to load PyO3 module
_NATIVE_MODULE: Any = None
try:
    import alos_native  # type: ignore[import-not-found]

    _NATIVE_MODULE = alos_native
except ImportError:
    _NATIVE_MODULE = None


def get_safety_evaluator() -> Any:
    """Return FastSafetyEvaluator if compiled, otherwise FallbackSafetyEvaluator."""
    if _NATIVE_MODULE is not None and hasattr(_NATIVE_MODULE, "FastSafetyEvaluator"):
        return _NATIVE_MODULE.FastSafetyEvaluator()
    return FallbackSafetyEvaluator()


def get_journal_writer(file_path: str) -> Any:
    """Return FastAuditJournalWriter if compiled, otherwise FallbackAuditJournalWriter."""
    if _NATIVE_MODULE is not None and hasattr(_NATIVE_MODULE, "FastAuditJournalWriter"):
        return _NATIVE_MODULE.FastAuditJournalWriter(file_path)
    return FallbackAuditJournalWriter(file_path)


def get_bm25_indexer(k1: float = 1.5, b: float = 0.75) -> Any:
    """Return FastBM25Indexer if compiled, otherwise FallbackBM25Indexer."""
    if _NATIVE_MODULE is not None and hasattr(_NATIVE_MODULE, "FastBM25Indexer"):
        return _NATIVE_MODULE.FastBM25Indexer(k1, b)
    return FallbackBM25Indexer(k1, b)
