"""Hexagonal Ring 3 SQLAlchemy/PostgreSQL audit and decision provenance adapters."""

import threading
from datetime import datetime
from typing import Any

from sqlalchemy import select

from alos.adapters.outbound.audit.jsonl_decision_log import _parse_seq, _to_decision_record
from alos.adapters.outbound.audit.telemetry_tracer import _enrich_trace
from alos.adapters.outbound.db.unit_of_work import SqlAlchemyUnitOfWork
from alos.db.models import AuditLogModel, DecisionRecordModel
from alos.domain.models.audit import AuditEvent, DecisionRecord


class PostgresAuditLogAdapter:
    """SQLAlchemy-backed adapter implementing AuditLoggerPort on system_audit_logs."""

    def __init__(self, uow: SqlAlchemyUnitOfWork) -> None:
        self._uow = uow

    def log_audit_event(self, event: AuditEvent) -> dict[str, Any]:
        """Persist an immutable AuditEvent row via SqlAlchemyUnitOfWork."""
        cols = event.model_dump(include={"step", "status", "reason"})
        ts = datetime.fromisoformat(event.timestamp)
        with self._uow.get_session() as s:
            s.add(AuditLogModel(timestamp=ts, **cols, metadata_json=dict(event.metadata)))
        return _enrich_trace(event.model_dump(mode="json"))

    def log_event(self, step: str, status: str, reason: Any = None, metadata: Any = None) -> Any:
        """Compatibility bridge constructing an AuditEvent and persisting to SQL."""
        ev = AuditEvent(step=step, status=status, reason=reason, metadata=dict(metadata or {}))
        return self.log_audit_event(ev)


class PostgresDecisionLogAdapter:
    """SQLAlchemy-backed adapter implementing DecisionLoggerPort on decision_records."""

    def __init__(self, uow: SqlAlchemyUnitOfWork) -> None:
        self._uow, self._lock, self._counter = uow, threading.Lock(), 0

    def log_decision_record(self, record: DecisionRecord) -> dict[str, Any]:
        """Persist an immutable DecisionRecord row with monotonic D-NNN continuity."""
        with self._lock, self._uow.get_session() as s:
            ids = s.scalars(select(DecisionRecordModel.decision_id))
            self._counter = max(self._counter + 1, max(map(_parse_seq, ids), default=0) + 1)
            self._counter = max(self._counter, _parse_seq(record.decision_id))
            did = f"D-{self._counter:03d}"
            cols = record.model_dump(mode="json", exclude={"trace_id", "span_id"})
            cols.update(decision_id=did, timestamp=datetime.fromisoformat(record.timestamp))
            s.add(DecisionRecordModel(**cols))
        return {**_enrich_trace(record.model_dump(mode="json")), "decision_id": did}

    def log_decision(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Compatibility bridge constructing a DecisionRecord and persisting to SQL."""
        return self.log_decision_record(_to_decision_record(*args, **kwargs))
