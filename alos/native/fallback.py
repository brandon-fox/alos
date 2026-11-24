"""Pure-Python Fallback Implementations for ALOS Native Extensions.

Spec: specs/003-rust-core-architectural-refactor/spec.md (FR-009)
Spec: specs/035-parallel-testing-and-qa-matrix/spec.md (FR-007, FR-011)
Constitution: Article VI (Human-Centric Non-Intrusiveness & Zero External Dependency Fallbacks)
"""

from __future__ import annotations

import contextlib
import math
import os
import sys
import threading
import time
from collections import Counter
from collections.abc import Generator
from typing import Any, ClassVar

_JOURNAL_LOCKS_GUARD = threading.Lock()
_JOURNAL_LOCKS: dict[str, threading.Lock] = {}


def _get_file_lock(abs_path: str) -> threading.Lock:
    with _JOURNAL_LOCKS_GUARD:
        lock = _JOURNAL_LOCKS.get(abs_path)
        if lock is None:
            lock = threading.Lock()
            _JOURNAL_LOCKS[abs_path] = lock
        return lock


@contextlib.contextmanager
def _interprocess_file_lock(lock_file_path: str) -> Generator[None, None, None]:
    fd = os.open(lock_file_path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        if sys.platform == "win32":
            import msvcrt

            os.lseek(fd, 0, os.SEEK_SET)
            if os.fstat(fd).st_size == 0:
                os.write(fd, b"0")
                os.lseek(fd, 0, os.SEEK_SET)
            while True:
                try:
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.002)
            try:
                yield
            finally:
                os.lseek(fd, 0, os.SEEK_SET)
                with contextlib.suppress(OSError):
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _tokenize_bm25(text: str) -> list[str]:
    return [tok for tok in text.lower().split() if tok]


class FallbackSafetyEvaluator:
    """Pure-Python fallback implementation of FastSafetyEvaluator."""

    HIGH_ACTION_TYPES: ClassVar[set[str]] = {
        "email_send",
        "calendar_delete",
        "financial_transaction",
        "email_create_draft",
    }
    MEDIUM_ACTION_TYPES: ClassVar[set[str]] = {
        "todoist_create_task",
        "google_calendar_create_event",
        "vault_update_note",
    }

    def classify_risk(self, action_type: str) -> str:
        """Classify action risk level."""
        if action_type == "web_search":
            return "LOW"
        if action_type in self.HIGH_ACTION_TYPES:
            return "HIGH"
        if action_type in self.MEDIUM_ACTION_TYPES:
            return "MEDIUM"
        return "HIGH"  # Fail-safe default

    def validate_calendar_preferences(
        self, action_type: str, start_time: str, preferences: list[str]
    ) -> dict[str, Any]:
        """Validate calendar action against preferences."""
        preferences_checked: list[str] = []
        if action_type == "google_calendar_create_event":
            for pref in preferences:
                if "No meetings scheduled after 5:00 PM" in pref:
                    preferences_checked.append(pref)
                    after_5pm = any(
                        f"T{h}:" in start_time for h in ["17", "18", "19", "20", "21", "22", "23"]
                    )
                    if after_5pm:
                        return {
                            "valid": False,
                            "critique": "Violates preference: No meetings scheduled after 5:00 PM",
                            "preferences_checked": preferences_checked,
                        }
        return {"valid": True, "critique": "VALID", "preferences_checked": preferences_checked}

    def validate_corrections(self, query: str, corrections: list[str]) -> dict[str, Any]:
        """Validate query against correction ledger."""
        corrections_checked: list[str] = []
        query_lower = query.lower()
        for corr in corrections:
            corrections_checked.append(corr)
            if "Delta" in corr and "flight" in query_lower and "delta" not in query_lower:
                return {
                    "valid": False,
                    "critique": f"Violates historical correction: {corr}",
                    "corrections_checked": corrections_checked,
                }
        return {"valid": True, "critique": "VALID", "corrections_checked": corrections_checked}


class FallbackAuditJournalWriter:
    """Thread- and process-safe pure-Python fallback of FastAuditJournalWriter."""

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        abs_path = os.path.abspath(file_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        self._lock = _get_file_lock(abs_path)
        self._ipc_lock_path = f"{abs_path}.lock"

    def append_record(self, record_json: str) -> bool:
        """Atomically append a single UTF-8 JSONL line across threads and OS processes."""
        payload = (record_json + "\n").encode("utf-8")
        flags = os.O_CREAT | os.O_WRONLY | os.O_APPEND
        with self._lock, _interprocess_file_lock(self._ipc_lock_path):
            fd = os.open(self.file_path, flags, 0o644)
            try:
                os.lseek(fd, 0, os.SEEK_END)
                os.write(fd, payload)
            finally:
                os.close(fd)
        return True

    def get_file_path(self) -> str:
        """Return target file path."""
        return self.file_path


class FallbackBM25Indexer:
    """Pure-Python Okapi BM25 fallback matching Rust FastBM25Indexer 1:1."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.chunks: list[dict[str, Any]] = []

    def add_chunk(
        self, header: str, file_name: str, file_path: str, source_type: str, content: str
    ) -> None:
        """Add text chunk with 3x header boost matching crates/alos_native/src/bm25.rs."""
        combined = f"{header} {header} {header} {content}"
        tokens = _tokenize_bm25(combined)
        self.chunks.append(
            {
                "header": header,
                "file_name": file_name,
                "file_path": file_path,
                "source_type": source_type,
                "content": content,
                "_tokens": tokens,
                "_tf": Counter(tokens),
            }
        )

    def clear(self) -> None:
        """Clear all indexed chunks."""
        self.chunks.clear()

    def _compute_idf(
        self, query_tokens: list[str], corpus: list[dict[str, Any]]
    ) -> dict[str, float]:
        n_docs = len(corpus)
        idf: dict[str, float] = {}
        for q_tok in set(query_tokens):
            df = sum(1 for c in corpus if q_tok in c["_tf"])
            idf[q_tok] = math.log(((n_docs - df + 0.5) / (df + 0.5)) + 1.0)
        return idf

    def search(
        self, query: str, top_k: int = 5, source_filter: str | None = None
    ) -> list[dict[str, Any]]:
        """Score indexed chunks via Okapi BM25 matching crates/alos_native/src/bm25.rs 1:1."""
        filtered = [
            c for c in self.chunks if source_filter is None or c["source_type"] == source_filter
        ]
        if not filtered or top_k <= 0:
            return []
        query_tokens = _tokenize_bm25(query)
        if not query_tokens:
            return [
                {
                    "header": c["header"],
                    "file_name": c["file_name"],
                    "file_path": c["file_path"],
                    "source_type": c["source_type"],
                    "content": c["content"],
                    "score": 0.0,
                }
                for c in filtered[:top_k]
            ]

        n_docs = len(filtered)
        total_len = sum(len(c["_tokens"]) for c in filtered)
        avg_dl = (total_len / n_docs) if total_len > 0 else 1.0
        idf_map = self._compute_idf(query_tokens, filtered)

        scored: list[dict[str, Any]] = []
        for chunk in filtered:
            doc_len = float(len(chunk["_tokens"]))
            tf_map: Counter[str] = chunk["_tf"]
            score = 0.0
            for q_tok in query_tokens:
                freq = float(tf_map.get(q_tok, 0))
                if freq <= 0.0:
                    continue
                denom = freq + self.k1 * (1.0 - self.b + self.b * (doc_len / avg_dl))
                score += idf_map[q_tok] * ((freq * (self.k1 + 1.0)) / denom)
            if score > 0.0:
                scored.append(
                    {
                        "header": chunk["header"],
                        "file_name": chunk["file_name"],
                        "file_path": chunk["file_path"],
                        "source_type": chunk["source_type"],
                        "content": chunk["content"],
                        "score": score,
                    }
                )
        scored.sort(key=lambda r: float(r["score"]), reverse=True)
        return scored[:top_k]
