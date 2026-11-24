"""Immutable Append-Only System Audit Logger.

Spec: specs/010-audit-and-decision-log/spec.md
Spec: specs/035-parallel-testing-and-qa-matrix/spec.md (FR-001, FR-007)
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from alos.logs.telemetry import get_active_span_context
from alos.native import get_journal_writer


def _resolve_default_audit_path() -> str:
    env_override = os.environ.get("ALOS_AUDIT_LOG_PATH")
    if env_override:
        return env_override
    alos_home = os.environ.get("ALOS_HOME")
    if alos_home:
        return os.path.join(alos_home, "logs", "system_audit.jsonl")
    return os.path.join(os.getcwd(), "logs", "system_audit.jsonl")


class SystemAuditLogger:
    """Immutable, append-only system audit logger (/logs/system_audit.jsonl)."""

    def __init__(self, log_file_path: str | None = None):
        self.log_file_path = log_file_path or _resolve_default_audit_path()
        parent = os.path.dirname(os.path.abspath(self.log_file_path))
        os.makedirs(parent, exist_ok=True)
        self._writer = get_journal_writer(self.log_file_path)

    def log_event(
        self,
        step: str,
        status: str,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Log structured audit event entry to append-only journal file."""
        active_span = get_active_span_context()
        record = {
            "timestamp": datetime.now().isoformat(),
            "step": step,
            "status": status,
            "reason": reason,
            "metadata": metadata or {},
            "trace_id": active_span.trace_id if active_span else None,
            "span_id": active_span.span_id if active_span else None,
        }
        self._writer.append_record(json.dumps(record))
        return record
