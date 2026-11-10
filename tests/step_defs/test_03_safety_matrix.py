"""Step definitions for 03_safety_matrix.feature."""

from typing import Any

from pytest_bdd import given, parsers, scenarios, then, when

from alos.core.evaluator import EvaluatorNode, RiskLevel
from alos.schemas.actions import EmailDraft, TodoistTaskCreate, WebSearchQuery

scenarios("../features/03_safety_matrix.feature")


@given(parsers.parse('a planned action "{action_desc}"'))
def step_planned_action(bdd_context: dict[str, Any], action_desc: str) -> None:
    action: Any
    if "Search web" in action_desc:
        action = WebSearchQuery(query="top rated driveway contractors")
    elif "Create Todoist task" in action_desc:
        action = TodoistTaskCreate(title="Buy driveway sealant", due_date="2026-08-05")
    elif "Send external email" in action_desc:
        action = EmailDraft(
            to_email="contractor@example.com",
            subject="Quote request",
            body="Please pave driveway",
        )
    else:
        action = WebSearchQuery(query=action_desc)

    bdd_context["action"] = action
    bdd_context["evaluator"] = EvaluatorNode(context=None)


@when("ALOS evaluates action risk level")
def step_evaluate_risk_level(bdd_context: dict[str, Any]) -> None:
    evaluator: EvaluatorNode = bdd_context["evaluator"]
    action = bdd_context["action"]
    risk = evaluator.classify_risk(action)
    bdd_context["risk_level"] = risk


@then(parsers.parse('the risk tier is categorized as "{expected_tier}"'))
def step_verify_risk_tier(bdd_context: dict[str, Any], expected_tier: str) -> None:
    risk: RiskLevel = bdd_context["risk_level"]
    assert risk.value == expected_tier


@then("ALOS executes the action without requiring real-time user confirmation")
def step_executes_automatically(bdd_context: dict[str, Any]) -> None:
    assert bdd_context["risk_level"] == RiskLevel.LOW


@then("ALOS validates Pydantic schema and executes automatically")
def step_validates_and_executes(bdd_context: dict[str, Any]) -> None:
    assert bdd_context["risk_level"] == RiskLevel.MEDIUM


@then("ALOS intercepts the action and requires explicit human approval before execution")
def step_requires_approval(bdd_context: dict[str, Any]) -> None:
    assert bdd_context["risk_level"] == RiskLevel.HIGH
