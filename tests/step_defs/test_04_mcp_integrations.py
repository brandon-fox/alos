"""Step definitions for 04_mcp_integrations.feature."""

from typing import Any

from pytest_bdd import given, parsers, scenarios, then, when

from alos.integrations.mcp_gateway import MCPGateway
from alos.schemas.actions import TodoistTaskCreate

scenarios("../features/04_mcp_integrations.feature")


@given(parsers.parse("an MCP Gateway connected to {service}"))
def step_mcp_gateway(bdd_context: dict[str, Any], service: str) -> None:
    gateway = MCPGateway(mock_mode=True)
    bdd_context["gateway"] = gateway


@when(
    parsers.parse(
        'an authorized action "{action_type}" with title "{title}" '
        'and due_date "{due_date}" is dispatched'
    )
)
def step_dispatch_todoist(
    bdd_context: dict[str, Any], action_type: str, title: str, due_date: str
) -> None:
    gateway: MCPGateway = bdd_context["gateway"]
    task_payload = TodoistTaskCreate(title=title, due_date=due_date)
    response = gateway.execute_tool("todoist_create_task", task_payload.model_dump())
    bdd_context["response"] = response


@then("the MCP Gateway translates payload into standard tool call")
def step_translates_payload(bdd_context: dict[str, Any]) -> None:
    assert bdd_context.get("response") is not None


@then("the task is successfully created on Todoist")
def step_task_created(bdd_context: dict[str, Any]) -> None:
    response = bdd_context["response"]
    assert response["status"] == "SUCCESS"
    assert response["task_id"] is not None


@when(parsers.parse('ALOS requests calendar events for "{target_date}"'))
def step_request_calendar(bdd_context: dict[str, Any], target_date: str) -> None:
    gateway: MCPGateway = bdd_context["gateway"]
    response = gateway.execute_tool("google_calendar_list_events", {"date": target_date})
    bdd_context["calendar_response"] = response


@then("the MCP Gateway queries Google Calendar MCP server")
def step_queries_gcal(bdd_context: dict[str, Any]) -> None:
    assert bdd_context.get("calendar_response") is not None


@then("returns structured calendar events matching the date")
def step_returns_gcal_events(bdd_context: dict[str, Any]) -> None:
    response = bdd_context["calendar_response"]
    assert response["status"] == "SUCCESS"
    assert isinstance(response["events"], list)
