from alos.engine.langgraph_n8n_loop import (
    N8nSelfReflectionGraph,
    N8nTaskState,
)
from alos.integrations.n8n_client import N8nClient, N8nExecutionResponse


def test_n8n_client_mock_execution():
    client = N8nClient(mock_mode=True)
    response = client.trigger_workflow(
        workflow_id="wf-123",
        payload={"task": "poll_data", "api_key": "secret"},
    )
    assert isinstance(response, N8nExecutionResponse)
    assert response.status_code == 200
    assert response.data.get("status") == "ok"


def test_langgraph_n8n_loop_success_initial():
    graph = N8nSelfReflectionGraph(mock_mode=True)
    initial_state: N8nTaskState = {
        "task_id": "task-001",
        "workflow_id": "wf-poll",
        "payload": {"query": "metrics", "api_key": "valid_token"},
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
    assert result["attempt_count"] == 1
    assert result["evaluation_valid"] is True


def test_langgraph_n8n_loop_self_correction():
    graph = N8nSelfReflectionGraph(mock_mode=True)
    # Payload missing api_key initially
    initial_state: N8nTaskState = {
        "task_id": "task-002",
        "workflow_id": "wf-poll",
        "payload": {"query": "metrics"},
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
    assert result["attempt_count"] == 2
    assert "api_key" in result["payload"]
    assert result["evaluation_valid"] is True


def test_langgraph_n8n_loop_max_retries_exceeded():
    graph = N8nSelfReflectionGraph(mock_mode=True)
    initial_state: N8nTaskState = {
        "task_id": "task-003",
        "workflow_id": "wf-always-fail",
        "payload": {"force_fail": True},
        "execution_output": None,
        "evaluation_valid": False,
        "critique": "",
        "attempt_count": 0,
        "max_attempts": 2,
        "status": "pending",
        "audit_logs": [],
    }
    result = graph.run(initial_state)
    assert result["status"] == "failed_max_retries"
    assert result["attempt_count"] == 2
    assert result["evaluation_valid"] is False
