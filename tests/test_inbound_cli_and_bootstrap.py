"""RED-first unit tests for PR-13a BootstrapContainer and inbound CLI subcommands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import inspect

import alos.application.ports.outbound as _p
from alos.application.use_cases.dual_loop_orchestrator import DualLoopOrchestrator
from alos.cli import main as alos_cli_main
from alos.config.bootstrap import BootstrapContainer
from alos.config.settings import ALOSSettings
from alos.db.session import DatabaseManager


@pytest.mark.mocked
def test_bootstrap_container_wires_ports_and_disposes(tmp_path: Path) -> None:
    """Verify BootstrapContainer builds canonical ports/use-cases and cleans up resources."""
    (v := tmp_path / "vault").mkdir()
    (v / "USER_PROFILE.md").write_text("name: Alex\n", encoding="utf-8")
    ap, dp = tmp_path / "a.jsonl", tmp_path / "d.jsonl"
    db = f"sqlite:///{(tmp_path / 'b.db').as_posix()}"
    cfg = ALOSSettings(
        vault_dir=str(v), audit_log_path=str(ap), decision_log_path=str(dp), database_url=db
    )
    with BootstrapContainer.build(cfg) as c:
        assert isinstance(c.vault, _p.VaultRepositoryPort)
        assert isinstance(c.memory, _p.MemoryStorePort)
        assert isinstance(c.audit_logger, _p.AuditLoggerPort)
        assert isinstance(c.decision_logger, _p.DecisionLoggerPort)
        assert isinstance(c.mcp_gateway, _p.MCPGatewayPort)
        assert isinstance(c.tracer, _p.TelemetryPort)
        assert isinstance(c.orchestrator, DualLoopOrchestrator) and c.get_db() is c.get_db()
        assert c.orchestrator.run("Send email summary")["status"] == "PENDING_APPROVAL"
    c.dispose()
    assert ap.exists() and dp.exists()
    with BootstrapContainer.build(cfg, use_postgres_logs=True) as pg:
        assert pg._db is not None


@pytest.mark.mocked
def test_cli_db_and_health_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify `alos health` and `alos db {upgrade,current}` run cleanly via BootstrapContainer."""
    db_url = f"sqlite:///{(tmp_path / 'cli_mig.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("ALOS_TELEMETRY_LOG_PATH", str(tmp_path / "t.jsonl"))
    for args in (["health"], ["db", "upgrade"], ["db", "current"]):
        with pytest.raises(SystemExit) as exc:
            alos_cli_main(args)
        assert exc.value.code == 0
    out = capsys.readouterr().out
    assert '"status"' in out and "0002" in out and json.loads(out.splitlines()[-1])["command"]
    mgr = DatabaseManager(db_url=db_url)
    assert inspect(mgr.engine).has_table("decision_records")
    mgr.engine.dispose()
    with pytest.raises(SystemExit) as err_exc:
        alos_cli_main(["db"])
    assert err_exc.value.code == 1
