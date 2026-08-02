"""Step definitions for langgraph_n8n_loop.feature."""

from typing import Any

from pytest_bdd import given, parsers, scenarios, then, when

from alos.engine.langgraph_n8n_loop import N8nSelfReflectionGraph, N8nTaskState

scenarios("../features/langgraph_n8n_loop.feature")


@given("an n8n polling task with valid payload")
def step_valid_n8n_payload(bdd_context: dict[str, Any]) -> None:
    bdd_context["initial_state"] = {
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


@when("the LangGraph self-reflection loop executes")
def step_execute_loop(bdd_context: dict[str, Any]) -> None:
    graph = N8nSelfReflectionGraph(mock_mode=True)
    initial_state: N8nTaskState = bdd_context["initial_state"]
    result = graph.run(initial_state)
    bdd_context["result"] = result


@then(parsers.parse('the task status is "{expected_status}"'))
def step_task_status(bdd_context: dict[str, Any], expected_status: str) -> None:
    result = bdd_context["result"]
    assert result["status"] == expected_status


@then(parsers.parse("attempt count is {expected_attempts:d}"))
def step_attempt_count(bdd_context: dict[str, Any], expected_attempts: int) -> None:
    result = bdd_context["result"]
    assert result["attempt_count"] == expected_attempts


@given(
    parsers.parse('an n8n polling task with initial missing required parameter "{missing_param}"')
)
def step_missing_param_payload(bdd_context: dict[str, Any], missing_param: str) -> None:
    bdd_context["initial_state"] = {
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
    bdd_context["missing_param"] = missing_param


@then(parsers.parse('the evaluation detects missing parameter "{missing_param}"'))
def step_detect_missing_param(bdd_context: dict[str, Any], missing_param: str) -> None:
    result = bdd_context["result"]
    assert missing_param in result.get("payload", {}) or result["attempt_count"] > 1


@then(parsers.parse('the payload is refined with parameter "{param_name}"'))
def step_refined_with_param(bdd_context: dict[str, Any], param_name: str) -> None:
    result = bdd_context["result"]
    assert param_name in result.get("payload", {})


@then("the loop retries execution")
def step_loop_retries(bdd_context: dict[str, Any]) -> None:
    result = bdd_context["result"]
    assert result["attempt_count"] > 1


@then('the final task status is "success"')
def step_final_status_success(bdd_context: dict[str, Any]) -> None:
    result = bdd_context["result"]
    assert result["status"] == "success"


@given("an n8n polling task that continuously fails validation")
def step_continuously_failing_task(bdd_context: dict[str, Any]) -> None:
    bdd_context["initial_state"] = {
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


@when(
    parsers.parse(
        "the LangGraph self-reflection loop executes with max attempts set to {max_att:d}"
    )
)
def step_execute_with_max_attempts(bdd_context: dict[str, Any], max_att: int) -> None:
    initial_state: N8nTaskState = bdd_context["initial_state"]
    initial_state["max_attempts"] = max_att
    graph = N8nSelfReflectionGraph(mock_mode=True)
    result = graph.run(initial_state)
    bdd_context["result"] = result


@then(parsers.parse('the loop terminates with status "{expected_status}"'))
def step_terminates_status(bdd_context: dict[str, Any], expected_status: str) -> None:
    result = bdd_context["result"]
    assert result["status"] == expected_status
