"""BDD step definitions for Twelve-Factor config and stream logging (Spec 036 PR-03).

Spec: specs/036-hexagonal-twelve-factor-refactor/spec.md (FR-3601, FR-3602, FR-3612)
"""

from __future__ import annotations

import ast
import importlib
import io
import json
import os
from pathlib import Path
from typing import Any

import pytest
import tomllib
from alembic.config import Config
from pydantic import SecretStr
from pytest_bdd import given, scenarios, then, when
from sqlalchemy import inspect

import alos.config.settings as settings_mod
import alos.crews.config as crews_config_mod
import alos.db.session as session_mod
from alembic import command
from alos.config.logging import configure_logging, get_logger
from alos.core.config import ALOSConfig
from alos.db.models import UserProfileModel
from alos.runtime import RuntimePaths

scenarios("../features/10_twelve_factor_config.feature")


@given("an isolated environment without CrewAI opt-out")
def step_clean_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bdd_context: Any) -> None:
    for var in ("CREWAI_TELEMETRY_OPT_OUT", "OTEL_SDK_DISABLED", "ALOS_WORKFLOWS_DIR"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///import_isolation_check.db")
    bdd_context["tmp"] = tmp_path


@when("settings, shims, and stream logging execute with env overrides")
def step_reload(monkeypatch: pytest.MonkeyPatch, bdd_context: Any, request: Any) -> None:
    for mod in (settings_mod, crews_config_mod, session_mod):
        importlib.reload(mod)
    files = ("alos/config/settings.py", "alos/crews/config.py", "alos/db/session.py")
    nodes = [s for p in files for s in ast.parse(Path(p).read_text("utf-8")).body]
    assert not [s for s in nodes if isinstance(s, ast.Expr) and isinstance(s.value, ast.Call)]
    assert "CREWAI_TELEMETRY_OPT_OUT" not in os.environ
    tmp = Path(bdd_context["tmp"])
    (tmp / ".env").write_text("ALOS_VAULT_DIR=./v2\nOPENAI_API_KEY=sk-sec\n", encoding="utf-8")
    monkeypatch.chdir(tmp)
    db_path, home = tmp / "shim.db", tmp / "home"
    monkeypatch.setenv("ALOS_MOCK_MODE", "false")
    monkeypatch.setenv("ALOS_OBSERVABILITY_PORT", "9555")
    monkeypatch.setenv("ALOS_LATENCY_SLO_MS", "1500.0")
    monkeypatch.setenv("ALOS_HOME", str(home))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    db = session_mod.DatabaseManager()
    request.addfinalizer(db.engine.dispose)
    out, err, tout, terr = io.StringIO(), io.StringIO(), io.StringIO(), io.StringIO()
    s_json = settings_mod.ALOSSettings(log_format="json")
    configure_logging(s_json, stream_out=out, stream_err=err).info("startup ok")
    get_logger("alos.runtime").error("db err", exc_info=RuntimeError("boom"))
    configure_logging(
        settings_mod.ALOSSettings(log_format="text"), stream_out=tout, stream_err=terr
    ).info("ok")
    bdd_context["res"] = (s_json, ALOSConfig().to_dict(), db, db_path, home)
    bdd_context["llm"] = crews_config_mod.LocalLLMConfig(is_mock=True).to_dict()
    bdd_context["rt"] = RuntimePaths.resolve()
    bdd_context["logs"] = (out.getvalue(), err.getvalue(), tout.getvalue())


@then("import stays clean while runtime settings, shims, and stdout/stderr logging pass")
def step_verify_mocked(bdd_context: Any) -> None:
    s, cfg, db, db_path, home = bdd_context["res"]
    assert "sqlite:///import_isolation_check.db" not in session_mod.DEFAULT_DB_URL
    assert s.vault_dir == "./v2" and s.workflows_dir == "workflows" and s.mock_mode is False
    assert isinstance(s.openai_api_key, SecretStr) and "sk-sec" not in str(s.openai_api_key)
    assert s.openai_api_key.get_secret_value() == "sk-sec"
    assert cfg["observability_port"] == 9555 and cfg["latency_slo_ms"] == 1500.0
    assert {"observability_host", "telemetry_enabled", "error_rate_threshold"} <= set(cfg)
    assert os.environ.get("CREWAI_TELEMETRY_OPT_OUT") == "true"
    assert bdd_context["llm"]["telemetry_disabled"]
    assert bdd_context["rt"].root == Path(home).resolve()
    assert Path(db.engine.url.database or "") == db_path
    out_p, err_p = json.loads(bdd_context["logs"][0]), json.loads(bdd_context["logs"][1])
    assert out_p["level"] == "INFO" and out_p["message"] == "startup ok"
    assert err_p["level"] == "ERROR" and "RuntimeError: boom" in err_p["exception"]
    assert "INFO alos: ok" in bdd_context["logs"][2]


@given("a live .env pointing DATABASE_URL to SQLite")
def step_live_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bdd_context: Any) -> None:
    url = f"sqlite:///{(tmp_path / 'live.db').as_posix()}"
    txt = f"DATABASE_URL={url}\nALOS_MOCK_MODE=true\n"
    (tmp_path / ".env").write_text(txt, encoding="utf-8")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    bdd_context["root"] = Path(__file__).resolve().parent.parent.parent


@when("ALOSSettings, DatabaseManager, and Alembic run against SQLite")
def step_live_db(bdd_context: Any, request: Any) -> None:
    db = session_mod.DatabaseManager(db_url=settings_mod.ALOSSettings().database_url)
    request.addfinalizer(db.engine.dispose)
    command.upgrade(Config(str(bdd_context["root"] / "alembic.ini")), "head")
    with db.get_session() as sess:
        sess.add(UserProfileModel(username="factor_tester", preferences={"log": "stdout"}))
    bdd_context["db"] = db


@then("SQLite persists records and pyproject declares deps and alos script")
def step_verify_live(bdd_context: Any) -> None:
    db: session_mod.DatabaseManager = bdd_context["db"]
    assert inspect(db.engine).has_table("compute_work_queue")
    with db.get_session() as sess:
        assert sess.query(UserProfileModel).filter_by(username="factor_tester").one().preferences
    data = tomllib.loads((bdd_context["root"] / "pyproject.toml").read_text(encoding="utf-8"))
    deps = data["project"]["dependencies"]
    assert any(d.startswith("pydantic-settings") for d in deps)
    assert any(d.startswith("pyyaml") for d in deps)
    assert data["project"]["scripts"]["alos"] == "alos.cli:main"
