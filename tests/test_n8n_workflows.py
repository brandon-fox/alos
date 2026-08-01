import json
from pathlib import Path

from alos.engine.langgraph_n8n_loop import N8nSelfReflectionGraph, N8nTaskState
from alos.integrations.n8n_client import N8nClient


def test_workflow_json_files_exist_and_valid():
    """Verify that all 3 n8n workflow export files exist and are valid JSON."""
    workflows_dir = Path("workflows") if Path("workflows").exists() else Path("workflows.example")
    if (workflows_dir / "n8n_human_approval_gate.json").exists():
        expected_files = [
            "n8n_human_approval_gate.json",
            "n8n_health_poll_self_correct.json",
            "n8n_vault_knowledge_ingestion.json",
        ]
    else:
        expected_files = [
            "wf-human-approval-gate.json",
            "wf-health-poll-self-correct.json",
            "wf-vault-knowledge-ingestion.json",
        ]

    for filename in expected_files:
        file_path = workflows_dir / filename
        assert file_path.exists(), f"Workflow file {filename} does not exist."
        content = json.loads(file_path.read_text(encoding="utf-8"))
        assert "name" in content
        assert "nodes" in content
        assert "connections" in content
        assert len(content["nodes"]) > 0


def test_human_approval_gate_workflow():
    client = N8nClient(mock_mode=True)

    # Missing required field task_id
    invalid_resp = client.trigger_workflow(
        workflow_id="wf-human-approval-gate",
        payload={"action_type": "email_send"},
    )
    assert invalid_resp.status_code == 400
    assert "Missing required parameter 'task_id'" in (invalid_resp.error or "")

    # Valid High Risk Action Payload
    high_risk_resp = client.trigger_workflow(
        workflow_id="wf-human-approval-gate",
        payload={
            "task_id": "task-001",
            "action_type": "email_send",
            "risk_level": "HIGH",
            "payload": {"to": "admin@example.com"},
        },
    )
    assert high_risk_resp.status_code == 200
    assert high_risk_resp.data["approval_required"] is True
    assert high_risk_resp.data["ticket_id"] == "tkt-task-001"


def test_health_poll_self_correct_workflow():
    client = N8nClient(mock_mode=True)

    # Healthy Execution
    healthy_resp = client.trigger_workflow(
        workflow_id="wf-health-poll-self-correct",
        payload={},
    )
    assert healthy_resp.status_code == 200
    assert healthy_resp.data["overall_status"] == "healthy"

    # Failing Health Execution (Simulated DB failure)
    failing_resp = client.trigger_workflow(
        workflow_id="wf-health-poll-self-correct",
        payload={"force_db_fail": True, "api_key": "valid_token"},
    )
    assert failing_resp.status_code == 500
    assert failing_resp.data.get("overall_status") == "degraded"
    assert "PostgreSQL connection failed" in (failing_resp.error or "")


def test_vault_knowledge_ingestion_workflow():
    client = N8nClient(mock_mode=True)

    # Missing content parameter
    invalid_resp = client.trigger_workflow(
        workflow_id="wf-vault-knowledge-ingestion",
        payload={"title": "Test Title"},
    )
    assert invalid_resp.status_code == 400
    assert "Missing required parameter 'content'" in (invalid_resp.error or "")

    # Valid Ingestion Payload
    valid_resp = client.trigger_workflow(
        workflow_id="wf-vault-knowledge-ingestion",
        payload={
            "title": "Agentic Architecture Note",
            "content": "Content regarding dual-loop reasoning.",
            "tags": ["#ai", "#alos"],
        },
    )
    assert valid_resp.status_code == 200
    assert valid_resp.data["note_title"] == "Agentic Architecture Note"
    assert "vault/ingested/agentic-architecture-note.md" in valid_resp.data["vault_path"]


def test_langgraph_reflection_loop_with_health_workflow():
    graph = N8nSelfReflectionGraph(mock_mode=True)
    initial_state: N8nTaskState = {
        "task_id": "task-health-01",
        "workflow_id": "wf-health-poll-self-correct",
        "payload": {"force_db_fail": True},  # missing api_key initially
        "execution_output": None,
        "evaluation_valid": False,
        "critique": "",
        "attempt_count": 0,
        "max_attempts": 3,
        "status": "pending",
        "audit_logs": [],
    }

    result = graph.run(initial_state)
    assert result["status"] == "success"
    assert result["attempt_count"] == 3
    assert "api_key" in result["payload"]
    assert result["evaluation_valid"] is True
