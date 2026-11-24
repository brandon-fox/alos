"""RED-first unit and live SQLite tests for Ring 3 audit, telemetry, and DB adapters."""

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from pydantic import ValidationError

import alos.adapters.outbound.audit as ap
import alos.adapters.outbound.db as dp
import alos.application.ports.outbound as ports
from alos import db, logs
from alos.domain.models import actions, audit, evaluation

_Q, _LOW = actions.WebSearchQuery(query="x"), evaluation.RiskLevel.LOW
_REC = audit.DecisionRecord(action_type="w", risk_level=_LOW, decision="APPROVED", rationale="ok")


@pytest.mark.mocked
def test_jsonl_restart_and_telemetry(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Recover D-006 after D-005 across restarts, enforce TelemetryPort, and keep shims."""
    df, sl, tr = tmp_path / "d.jsonl", logging.getLogger("alos.t"), ap.InMemoryTelemetryAdapter()
    df.write_text("\n".join([json.dumps({"decision_id": "D-005"}), "", "{bad"]), "utf-8")
    dl = ap.JsonlDecisionLogAdapter(str(df), stream_logger=sl)
    al = ap.JsonlAuditLogAdapter(str(tmp_path / "a.jsonl"), stream_logger=sl)
    assert isinstance(dl, ports.DecisionLoggerPort) and isinstance(al, ports.AuditLoggerPort)
    assert issubclass(logs.DecisionLogger, type(dl)) and isinstance(tr, ports.TelemetryPort)
    with caplog.at_level(logging.INFO, logger="alos.t"), tr.span("op") as sp:
        with pytest.raises(ValidationError):
            setattr(sp, "".join(["bad"]), 1)
        r6, r7 = dl.log_decision_record(_REC), dl.log_decision("q", _Q, "LOW", "APPROVED", "ok")
        e1 = al.log_audit_event(audit.AuditEvent(step="s1", status="OK"))
    tr.observe_histogram("h1", tr.set_gauge("g1", tr.inc_counter("c1")))
    assert (r6["decision_id"], r7["decision_id"], e1["span_id"]) == ("D-006", "D-007", sp.span_id)
    assert "D-006" in caplog.text and "# TYPE h1 histogram" in tr.render_prometheus()
    assert logs.RuntimeMonitor(tracer=tr, vault_dir=str(tmp_path)).check_health().status


@pytest.mark.live
def test_threads_and_postgres_uow(tmp_path: Path) -> None:
    """Verify thread-safe JSONL appends and SQLite/Postgres UoW provenance continuity."""
    dl = ap.JsonlDecisionLogAdapter(str(tmp_path / "c.jsonl"))
    with ThreadPoolExecutor(max_workers=6) as pool:
        got = sorted(str(r["decision_id"]) for r in pool.map(dl.log_decision_record, [_REC] * 8))
    uow = dp.SqlAlchemyUnitOfWork(f"sqlite:///{(tmp_path / 'prov.db').as_posix()}")
    uow.create_all_tables()
    pa, pd = dp.PostgresAuditLogAdapter(uow), dp.PostgresDecisionLogAdapter(uow)
    pa.log_event("boot", "OK", metadata={"k": 1})
    d1 = pd.log_decision_record(_REC)
    d2 = dp.PostgresDecisionLogAdapter(uow).log_decision("t", _Q, _LOW, "REJECTED", "r")
    assert got == [f"D-{i:03d}" for i in range(1, 9)]
    assert (d1["decision_id"], d2["decision_id"]) == ("D-001", "D-002")
    assert isinstance(uow, db.DatabaseManager) and isinstance(pa, ports.AuditLoggerPort)
    with uow.get_session() as s:
        assert isinstance(pd, ports.DecisionLoggerPort)
        assert s.query(db.DecisionRecordModel).count() == 2
    uow.dispose()
