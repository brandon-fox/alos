"""Hexagonal Ring 3 JSONL system audit adapter implementing AuditLoggerPort."""

import json
import logging
import threading
from typing import Any

from alos.adapters.outbound.audit.telemetry_tracer import _enrich_trace, _resolve_journal_path
from alos.domain.models.audit import AuditEvent
from alos.native import get_journal_writer


class JsonlAuditLogAdapter:
    """Append-only JSONL adapter for immutable AuditEvent records (Spec 036, FR-3612)."""

    def __init__(self, log_file_path: str | None = None, *, stream_logger: Any = None) -> None:
        p = _resolve_journal_path(log_file_path, "audit_log_path", "system_audit.jsonl")
        self.log_file_path, self._lock, self._writer = p, threading.Lock(), get_journal_writer(p)
        self._stream: logging.Logger | None = stream_logger

    def log_audit_event(self, event: AuditEvent) -> dict[str, Any]:
        """Persist an immutable AuditEvent to the append-only journal and return record dict."""
        out = _enrich_trace(event.model_dump(mode="json"))
        with self._lock:
            self._writer.append_record(json.dumps(out))
        if self._stream is not None:
            self._stream.info("audit %s %s", out["step"], out["status"])
        return out

    def log_event(self, step: str, status: str, reason: Any = None, metadata: Any = None) -> Any:
        """Compatibility bridge constructing an AuditEvent and delegating persistence."""
        ev = AuditEvent(step=step, status=status, reason=reason, metadata=dict(metadata or {}))
        return self.log_audit_event(ev)
