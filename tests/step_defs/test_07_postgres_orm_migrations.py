"""Step definitions for 07_postgres_orm_migrations.feature."""

from pathlib import Path
from typing import Any

from alembic.config import Config
from pytest_bdd import given, scenarios, then, when
from sqlalchemy import inspect

from alembic import command
from alos.db.base import Base
from alos.db.models import (
    AuditLogModel,
    DecisionRecordModel,
    ExecutionStateModel,
    UserProfileModel,
)
from alos.db.session import DatabaseManager

scenarios("../features/07_postgres_orm_migrations.feature")


@given("declarative Base model in alos.db.base")
def step_declarative_base(bdd_context: dict[str, Any]) -> None:
    assert Base is not None


@when(
    "AuditLogModel, DecisionRecordModel, ExecutionStateModel, and UserProfileModel are instantiated"
)
def step_instantiate_models(bdd_context: dict[str, Any]) -> None:
    user = UserProfileModel(username="alex", preferences={"dark_mode": True})
    audit = AuditLogModel(step="test", status="SUCCESS")
    decision = DecisionRecordModel(
        decision_id="D-1",
        trigger="test",
        action_type="test",
        risk_level="LOW",
        decision="APPROVED",
        rationale="pass",
        constitution_articles_checked=[],
        preferences_checked=[],
        corrections_checked=[],
        alternatives_considered=[],
        self_correction_rounds=0,
    )
    exec_state = ExecutionStateModel(workflow_id="wf-1", status="SUCCESS")

    bdd_context["models"] = [user, audit, decision, exec_state]


@then("model attributes must map correctly to relational column definitions and primary keys")
def step_verify_attributes(bdd_context: dict[str, Any]) -> None:
    models = bdd_context["models"]
    assert models[0].username == "alex"
    assert models[1].status == "SUCCESS"
    assert models[2].decision_id == "D-1"
    assert models[3].workflow_id == "wf-1"


@given("alembic.ini configuration bound to alos.db.base.Base.metadata")
def step_alembic_config(tmp_path: Path, bdd_context: dict[str, Any]) -> None:
    db_file = tmp_path / "test_migration.db"
    db_url = f"sqlite:///{db_file}"
    db_manager = DatabaseManager(db_url=db_url)

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    bdd_context["alembic_cfg"] = alembic_cfg
    bdd_context["db_manager"] = db_manager


@when("alembic upgrade head and downgrade base commands run")
def step_run_alembic_commands(bdd_context: dict[str, Any]) -> None:
    alembic_cfg: Config = bdd_context["alembic_cfg"]
    db_manager: DatabaseManager = bdd_context["db_manager"]

    command.upgrade(alembic_cfg, "head")

    inspector = inspect(db_manager.engine)
    bdd_context["post_upgrade_has_tables"] = inspector.has_table(
        "system_audit_logs"
    ) and inspector.has_table("decision_records")

    command.downgrade(alembic_cfg, "base")

    inspector_post = inspect(db_manager.engine)
    bdd_context["post_downgrade_has_tables"] = inspector_post.has_table("system_audit_logs")


@then("database schema migrations must execute reproducibly without errors")
def step_verify_migrations(bdd_context: dict[str, Any]) -> None:
    assert bdd_context["post_upgrade_has_tables"] is True
    assert bdd_context["post_downgrade_has_tables"] is False
