"""Immutable Append-Only System Audit Logger.

Spec: specs/05-audit-and-decision-log/spec.md
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from alos.native import get_journal_writer


class SystemAuditLogger:
    """Immutable, append-only system audit logger (/logs/system_audit.jsonl)."""

    def __init__(self, log_file_path: str | None = None):
        if log_file_path:
            self.log_file_path = log_file_path
        else:
            self.log_file_path = os.path.join(os.getcwd(), "logs", "system_audit.jsonl")

        # Ensure log folder exists
        os.makedirs(os.path.dirname(self.log_file_path), exist_ok=True)
        self._writer = get_journal_writer(self.log_file_path)

    def log_event(
        self,
        step: str,
        status: str,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Log structured audit event entry to append-only journal file."""
        record = {
            "timestamp": datetime.now().isoformat(),
            "step": step,
            "status": status,
            "reason": reason,
            "metadata": metadata or {},
        }
        self._writer.append_record(json.dumps(record))
        return record
