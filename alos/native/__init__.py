"""ALOS Native Bridge Package initializing PyO3 compiled bindings with pure-Python fallbacks.

Spec: specs/002-rust-core-architectural-refactor/spec.md (FR-009)
"""

from __future__ import annotations

import logging

from alos.native.bridge import (
    get_bm25_indexer,
    get_journal_writer,
    get_safety_evaluator,
)

logger = logging.getLogger(__name__)

# Dynamic import detection for PyO3 compiled extension alos_native
HAS_NATIVE_EXTENSION: bool = False
try:
    import alos_native  # type: ignore[import-not-found] # noqa: F401

    HAS_NATIVE_EXTENSION = True
    logger.info("Successfully loaded alos_native PyO3 Rust extension module.")
except ImportError:
    HAS_NATIVE_EXTENSION = False
    logger.debug("alos_native PyO3 Rust extension not found; using pure-Python fallback drivers.")

__all__ = [
    "HAS_NATIVE_EXTENSION",
    "get_bm25_indexer",
    "get_journal_writer",
    "get_safety_evaluator",
]
