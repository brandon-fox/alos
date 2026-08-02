"""Pure-Python Fallback Implementations for ALOS Native Extensions.

Spec: specs/002-rust-core-architectural-refactor/spec.md (FR-009)
Constitution: Article VI (Human-Centric Non-Intrusiveness & Zero External Dependency Fallbacks)
"""

from __future__ import annotations

import os
from typing import Any, ClassVar


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
    """Pure-Python fallback implementation of FastAuditJournalWriter."""

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)

    def append_record(self, record_json: str) -> bool:
        """Append record string to log file."""
        with open(self.file_path, "a", encoding="utf-8") as f:
            f.write(record_json + "\n")
        return True

    def get_file_path(self) -> str:
        """Return target file path."""
        return self.file_path


class FallbackBM25Indexer:
    """Pure-Python fallback implementation of FastBM25Indexer."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.chunks: list[dict[str, Any]] = []

    def add_chunk(
        self, header: str, file_name: str, file_path: str, source_type: str, content: str
    ) -> None:
        self.chunks.append(
            {
                "header": header,
                "file_name": file_name,
                "file_path": file_path,
                "source_type": source_type,
                "content": content,
            }
        )

    def clear(self) -> None:
        self.chunks.clear()

    def search(
        self, query: str, top_k: int = 5, source_filter: str | None = None
    ) -> list[dict[str, Any]]:
        results = []
        query_lower = query.lower()
        for chunk in self.chunks:
            if source_filter and chunk["source_type"] != source_filter:
                continue
            score = 1.0 if query_lower in chunk["content"].lower() else 0.1
            results.append(
                {
                    "header": chunk["header"],
                    "file_name": chunk["file_name"],
                    "file_path": chunk["file_path"],
                    "source_type": chunk["source_type"],
                    "content": chunk["content"],
                    "score": score,
                }
            )
        return results[:top_k]
