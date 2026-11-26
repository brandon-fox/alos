"""Inbound CLI adapter wiring `alos db`, `alos health`, and container lifecycle (ADR-0024)."""

from __future__ import annotations

import argparse
import json
import logging
from io import StringIO
from pathlib import Path
from typing import Any

from alembic.config import Config

from alembic import command
from alos.config.bootstrap import BootstrapContainer
from alos.core.config import ALOSConfig
from alos.logs.monitor import RuntimeMonitor

logger = logging.getLogger(__name__)


def register_inbound_subcommands(subparsers: Any) -> None:
    """Register `db` and `health` subcommands onto the root CLI parser."""
    db_sub = subparsers.add_parser("db", help="Run Alembic migrations").add_subparsers(
        dest="db_action"
    )
    up_p = db_sub.add_parser("upgrade", help="Upgrade schema to target revision")
    up_p.add_argument("revision", nargs="?", default="head")
    for sub in (up_p, db_sub.add_parser("current", help="Show current Alembic revision")):
        sub.add_argument("--db-url", default=None, help="Override SQLAlchemy URL")
    subparsers.add_parser("health", help="Evaluate runtime health and readiness probes")


def _run_db(args: argparse.Namespace, container: BootstrapContainer) -> tuple[int, str]:
    act = getattr(args, "db_action", None)
    if act not in ("upgrade", "current"):
        logger.warning("Missing or invalid db action: %s", act)
        return 1, "Error: specify db action {upgrade,current}."
    root_ini = Path(__file__).resolve().parents[3] / "alembic.ini"
    ini, buf = str(root_ini if root_ini.exists() else Path("alembic.ini")), StringIO()
    cfg = Config(ini, stdout=buf)
    cfg.set_main_option(
        "sqlalchemy.url", getattr(args, "db_url", None) or container.settings.database_url
    )
    command.upgrade(cfg, args.revision) if act == "upgrade" else command.current(cfg)
    rev = args.revision if act == "upgrade" else buf.getvalue().strip()
    return 0, json.dumps({"status": "OK", "command": act, "revision": rev})


def dispatch_inbound_command(
    args: argparse.Namespace, config: ALOSConfig
) -> tuple[int, str] | None:
    """Execute `db` or `health` commands cleanly, returning (exit_code, output) or None."""
    if args.subcommand not in ("db", "health"):
        return None
    with BootstrapContainer.build(config) as c:
        if args.subcommand == "db":
            return _run_db(args, c)
        rep = RuntimeMonitor(config=c.settings, tracer=c.tracer).check_health()
        return (1 if rep.status == "UNHEALTHY" else 0), rep.model_dump_json(indent=2)
