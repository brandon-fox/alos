import json

# TDD Tests mapping directly to SDD System Spec & BDD Gherkin Feature Specifications
# Feature spec traceability:
#   test_01  → specs/01-context-synthesis/spec.md
#   test_02  → specs/02-dual-loop-reasoning/spec.md
#   test_03  → specs/03-safety-matrix/spec.md
#   test_04  → specs/04-mcp-integrations/spec.md
#   test_05  → specs/05-audit-and-decision-log/spec.md (SystemAuditLogger)
#   test_06  → specs/02-dual-loop-reasoning/spec.md (end-to-end)
#   test_07  → specs/05-audit-and-decision-log/spec.md (DecisionLogger entry structure)
#   test_08  → specs/05-audit-and-decision-log/spec.md (alternatives_considered on rejection)


def test_01_context_synthesis_from_vault(tmp_path):
    """BDD Scenario: Assemble context from Markdown vault files"""
    from alos.core.context_assembler import ContextAssembler

    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    (vault_dir / "USER_PROFILE.md").write_text(
        "User: Alex\nTimezone: America/New_York", encoding="utf-8"
    )
    (vault_dir / "PREFERENCES.md").write_text(
        "Rules:\n- No meetings scheduled after 5:00 PM", encoding="utf-8"
    )
    (vault_dir / "CORRECTION_LEDGER.md").write_text(
        "History:\n- Never book flights without checking Delta options first", encoding="utf-8"
    )

    assembler = ContextAssembler(vault_dir=str(vault_dir))
    context = assembler.assemble_context(
        user_query="Plan my trip to San Francisco and update my schedule"
    )

    assert "No meetings scheduled after 5:00 PM" in context.preferences
    assert "Never book flights without checking Delta options first" in context.corrections
    assert context.profile["User"] == "Alex"


def test_02_dual_loop_reasoning_evaluator_rejection(tmp_path):
    """BDD Scenario: Planner generates an invalid plan that violates user preferences"""
    from alos.core.context_assembler import ContextPayload
    from alos.core.evaluator import EvaluatorNode
    from alos.schemas.actions import GoogleCalendarEvent

    context = ContextPayload(
        profile={"User": "Alex"},
        preferences=["No meetings scheduled after 5:00 PM"],
        corrections=[],
    )

    evaluator = EvaluatorNode(context=context)
    invalid_event = GoogleCalendarEvent(
        title="Team Sync",
        start_time="2026-08-01T17:30:00",  # 5:30 PM violates preference
        end_time="2026-08-01T18:00:00",
    )

    evaluation = evaluator.evaluate_action(action=invalid_event)

    assert evaluation.valid is False
    assert "Violates preference: No meetings scheduled after 5:00 PM" in evaluation.critique


def test_02_dual_loop_reasoning_evaluator_approval(tmp_path):
    """BDD Scenario: Planner generates a valid plan that complies with preferences"""
    from alos.core.context_assembler import ContextPayload
    from alos.core.evaluator import EvaluatorNode
    from alos.schemas.actions import GoogleCalendarEvent

    context = ContextPayload(
        profile={"User": "Alex"},
        preferences=["No meetings scheduled after 5:00 PM"],
        corrections=[],
    )

    evaluator = EvaluatorNode(context=context)
    valid_event = GoogleCalendarEvent(
        title="Team Sync",
        start_time="2026-08-01T14:00:00",  # 2:00 PM valid
        end_time="2026-08-01T15:00:00",
    )

    evaluation = evaluator.evaluate_action(action=valid_event)

    assert evaluation.valid is True
    assert evaluation.critique == "VALID"


def test_03_safety_matrix_risk_classification():
    """BDD Scenarios: Risk tier categorization (Low, Medium, High)"""
    from alos.core.evaluator import EvaluatorNode, RiskLevel
    from alos.schemas.actions import EmailDraft, TodoistTaskCreate, WebSearchQuery

    evaluator = EvaluatorNode(context=None)

    # Low risk
    low_action = WebSearchQuery(query="top rated driveway contractors")
    assert evaluator.classify_risk(low_action) == RiskLevel.LOW

    # Medium risk
    med_action = TodoistTaskCreate(title="Buy driveway sealant", due_date="2026-08-05")
    assert evaluator.classify_risk(med_action) == RiskLevel.MEDIUM

    # High risk
    high_action = EmailDraft(
        to_email="contractor@example.com", subject="Quote request", body="Please pave driveway"
    )
    assert evaluator.classify_risk(high_action) == RiskLevel.HIGH


def test_04_mcp_gateway_todoist_and_google():
    """BDD Scenario: Create Todoist task and query Google Calendar via MCP Gateway"""
    from alos.integrations.mcp_gateway import MCPGateway
    from alos.schemas.actions import TodoistTaskCreate

    gateway = MCPGateway(mock_mode=True)
    task_payload = TodoistTaskCreate(title="Schedule quarterly review", due_date="2026-08-05")

    response = gateway.execute_tool("todoist_create_task", task_payload.model_dump())
    assert response["status"] == "SUCCESS"
    assert response["task_id"] is not None

    calendar_response = gateway.execute_tool("google_calendar_list_events", {"date": "2026-08-01"})
    assert calendar_response["status"] == "SUCCESS"
    assert isinstance(calendar_response["events"], list)


def test_05_audit_logging_append_only(tmp_path):
    """BDD Scenario: Audit logger appends state transitions to audit log file"""
    from alos.logs.system_audit import SystemAuditLogger

    log_file = tmp_path / "logs" / "system_audit.jsonl"
    logger = SystemAuditLogger(log_file_path=str(log_file))

    logger.log_event(step="Context Assembly", status="SUCCESS", metadata={"item_count": 3})
    logger.log_event(step="Evaluator Check", status="REJECTED", reason="Preference Violation")

    assert log_file.exists()
    lines = log_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2

    record_1 = json.loads(lines[0])
    assert record_1["step"] == "Context Assembly"
    assert record_1["status"] == "SUCCESS"

    record_2 = json.loads(lines[1])
    assert record_2["step"] == "Evaluator Check"
    assert record_2["status"] == "REJECTED"
    assert record_2["reason"] == "Preference Violation"


def test_06_end_to_end_state_graph_dual_loop(tmp_path):
    """Integration Test: Full dual-loop execution with self-correction
    Spec: specs/02-dual-loop-reasoning/spec.md — User Story 2
    """
    from alos.core.graph import ALOSStateGraph

    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    (vault_dir / "USER_PROFILE.md").write_text("User: Alex", encoding="utf-8")
    (vault_dir / "PREFERENCES.md").write_text(
        "- No meetings scheduled after 5:00 PM", encoding="utf-8"
    )
    (vault_dir / "CORRECTION_LEDGER.md").write_text(
        "- Always set priority 1 for urgent tasks", encoding="utf-8"
    )

    log_file = tmp_path / "logs" / "system_audit.jsonl"

    graph = ALOSStateGraph(vault_dir=str(vault_dir), audit_log_path=str(log_file))

    # Test query that Planner initially tries at 5:30 PM, Evaluator rejects,
    # Planner self-corrects to 2:00 PM
    result = graph.run(user_query="Schedule meeting Team Sync for today")

    assert result["status"] == "SUCCESS"
    assert result["final_action"]["start_time"] == "2026-08-01T14:00:00"
    assert result["self_correction_attempts"] >= 1


def test_07_decision_log_entry_structure(tmp_path):
    """TDD — RED phase: DecisionLogger must write all 12 required ADR fields.
    Spec: specs/05-audit-and-decision-log/spec.md — FR-005, FR-006, SC-001, SC-003
    """
    from alos.core.evaluator import RiskLevel
    from alos.logs.decision_log import DecisionLogger
    from alos.schemas.actions import GoogleCalendarEvent

    log_file = tmp_path / "logs" / "decision_log.jsonl"
    logger = DecisionLogger(log_file_path=str(log_file))

    action = GoogleCalendarEvent(
        title="Team Sync", start_time="2026-08-01T14:00:00", end_time="2026-08-01T15:00:00"
    )

    logger.log_decision(
        trigger="Schedule meeting Team Sync for today",
        action=action,
        risk_level=RiskLevel.MEDIUM,
        decision="APPROVED",
        rationale="Event at 14:00 satisfies 'No meetings after 5:00 PM'.",
        constitution_articles_checked=["I §1", "V"],
        preferences_checked=["No meetings scheduled after 5:00 PM"],
        corrections_checked=[],
        alternatives_considered=[],
        self_correction_rounds=0,
    )

    assert log_file.exists()
    lines = log_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 1

    record = json.loads(lines[0])
    # Verify all 12 required fields per FR-006
    required_fields = [
        "timestamp",
        "decision_id",
        "trigger",
        "action_type",
        "risk_level",
        "decision",
        "rationale",
        "constitution_articles_checked",
        "preferences_checked",
        "corrections_checked",
        "alternatives_considered",
        "self_correction_rounds",
    ]
    for field in required_fields:
        assert field in record, f"Missing required field: {field}"

    assert record["decision_id"].startswith("D-")
    assert record["trigger"] == "Schedule meeting Team Sync for today"
    assert record["action_type"] == "google_calendar_create_event"
    assert record["risk_level"] == "MEDIUM"
    assert record["decision"] == "APPROVED"
    assert record["constitution_articles_checked"] == ["I §1", "V"]
    assert record["self_correction_rounds"] == 0


def test_08_decision_log_alternatives_on_rejection(tmp_path):
    """TDD — RED phase: After one self-correction round, alternatives_considered must be non-empty.
    Spec: specs/05-audit-and-decision-log/spec.md — FR-008, SC-002
    """
    from alos.core.graph import ALOSStateGraph

    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    (vault_dir / "USER_PROFILE.md").write_text("User: Alex", encoding="utf-8")
    (vault_dir / "PREFERENCES.md").write_text(
        "- No meetings scheduled after 5:00 PM", encoding="utf-8"
    )
    (vault_dir / "CORRECTION_LEDGER.md").write_text("", encoding="utf-8")

    audit_log = tmp_path / "logs" / "system_audit.jsonl"
    decision_log = tmp_path / "logs" / "decision_log.jsonl"

    graph = ALOSStateGraph(
        vault_dir=str(vault_dir), audit_log_path=str(audit_log), decision_log_path=str(decision_log)
    )
    result = graph.run(user_query="Schedule meeting Team Sync for today")

    assert result["status"] == "SUCCESS"
    assert result["self_correction_attempts"] >= 1

    # Read the APPROVED decision record (last line in decision_log.jsonl)
    lines = decision_log.read_text(encoding="utf-8").strip().split("\n")
    approved_record = None
    for line in lines:
        rec = json.loads(line)
        if rec["decision"] == "APPROVED":
            approved_record = rec
            break

    assert approved_record is not None, "No APPROVED record found in decision log"
    assert len(approved_record["alternatives_considered"]) >= 1, (
        "alternatives_considered must contain at least one rejected alternative"
    )
    assert approved_record["self_correction_rounds"] >= 1


def test_09_postgres_orm_and_alembic_migrations(tmp_path):
    """BDD Scenario & Spec 07: Validate PostgreSQL ORM model management and Alembic migrations.
    Spec: specs/07-postgres-orm-migrations/spec.md
    """
    from alembic.config import Config
    from sqlalchemy import inspect

    from alembic import command
    from alos.db.models import (
        AuditLogModel,
        DecisionRecordModel,
        ExecutionStateModel,
        UserProfileModel,
    )
    from alos.db.session import DatabaseManager

    db_file = tmp_path / "test_alos.db"
    db_url = f"sqlite:///{db_file}"

    # 1. ORM Model CRUD Operations via DatabaseManager
    db_manager = DatabaseManager(db_url=db_url)
    db_manager.create_all_tables()

    with db_manager.get_session() as session:
        user = UserProfileModel(
            username="alex_dev",
            preferences={"theme": "dark", "notifications": True},
        )
        session.add(user)

        audit = AuditLogModel(
            step="Context Assembly",
            status="SUCCESS",
            reason="Vault scanned",
            metadata_json={"files_processed": 3},
        )
        session.add(audit)

        decision = DecisionRecordModel(
            decision_id="D-0001",
            trigger="Schedule sync meeting",
            action_type="google_calendar_create_event",
            risk_level="MEDIUM",
            decision="APPROVED",
            rationale="Event within allowable working hours",
            constitution_articles_checked=["I §1"],
            preferences_checked=["No meetings after 5pm"],
            corrections_checked=[],
            alternatives_considered=[],
            self_correction_rounds=0,
        )
        session.add(decision)

        exec_state = ExecutionStateModel(
            workflow_id="wf-101",
            status="COMPLETED",
            payload={"step": "final"},
        )
        session.add(exec_state)

    # Verify query retrieves ORM objects correctly
    with db_manager.get_session() as session:
        queried_user = session.query(UserProfileModel).filter_by(username="alex_dev").one()
        assert queried_user.preferences["theme"] == "dark"

        queried_audit = session.query(AuditLogModel).filter_by(step="Context Assembly").one()
        assert queried_audit.status == "SUCCESS"

        queried_decision = session.query(DecisionRecordModel).filter_by(decision_id="D-0001").one()
        assert queried_decision.decision == "APPROVED"

        queried_exec = session.query(ExecutionStateModel).filter_by(workflow_id="wf-101").one()
        assert queried_exec.status == "COMPLETED"

    db_manager.drop_all_tables()

    # 2. Programmatic Alembic Migration Upgrade & Downgrade Execution
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # Upgrade to head (applies revision 0001)
    command.upgrade(alembic_cfg, "head")

    # Verify tables created by migration exist
    inspector = inspect(db_manager.engine)
    assert inspector.has_table("alembic_version")
    assert inspector.has_table("system_audit_logs")
    assert inspector.has_table("decision_records")
    assert inspector.has_table("execution_states")
    assert inspector.has_table("user_profiles")

    # Downgrade to base (rolls back revision 0001)
    command.downgrade(alembic_cfg, "base")
    inspector_post_downgrade = inspect(db_manager.engine)
    assert not inspector_post_downgrade.has_table("system_audit_logs")
    assert not inspector_post_downgrade.has_table("decision_records")


def test_19_open_source_workflows_dir_configuration(monkeypatch, tmp_path):
    """BDD Scenario & Spec 19: Open-source configuration supports custom ALOS_WORKFLOWS_DIR
    Spec: specs/19-open-source-dual-repo-architecture/spec.md
    """
    from alos.core.config import ALOSConfig

    # Default workflows_dir fallback
    monkeypatch.delenv("ALOS_WORKFLOWS_DIR", raising=False)
    default_config = ALOSConfig()
    assert default_config.workflows_dir == "workflows"

    # Custom ALOS_WORKFLOWS_DIR via environment variable
    custom_dir = str(tmp_path / "custom_workflows")
    monkeypatch.setenv("ALOS_WORKFLOWS_DIR", custom_dir)
    custom_config = ALOSConfig()
    assert custom_config.workflows_dir == custom_dir
