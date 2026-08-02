"""Step definitions for 02_dual_loop_reasoning.feature."""

from typing import Any

from pytest_bdd import given, parsers, scenarios, then, when

from alos.core.context_assembler import ContextPayload
from alos.core.evaluator import EvaluatorNode
from alos.schemas.actions import GoogleCalendarEvent

scenarios("../features/02_dual_loop_reasoning.feature")


@given(parsers.parse('the context preference "{pref}"'))
def step_context_preference(bdd_context: dict[str, Any], pref: str) -> None:
    context = ContextPayload(
        profile={"User": "Alex"},
        preferences=[pref],
        corrections=[],
    )
    bdd_context["context"] = context
    bdd_context["evaluator"] = EvaluatorNode(context=context)


@when(parsers.parse('the Planner drafts a calendar event for "{title} at {time_str}"'))
def step_planner_drafts_event(bdd_context: dict[str, Any], title: str, time_str: str) -> None:
    # Convert "5:30 PM" -> "2026-08-01T17:30:00", "2:00 PM" -> "2026-08-01T14:00:00"
    if "5:30 PM" in time_str:
        iso_start = "2026-08-01T17:30:00"
        iso_end = "2026-08-01T18:00:00"
    elif "2:00 PM" in time_str:
        iso_start = "2026-08-01T14:00:00"
        iso_end = "2026-08-01T15:00:00"
    else:
        iso_start = f"2026-08-01T{time_str}:00"
        iso_end = f"2026-08-01T{time_str}:30"

    event = GoogleCalendarEvent(
        title=title,
        start_time=iso_start,
        end_time=iso_end,
    )
    evaluator: EvaluatorNode = bdd_context["evaluator"]
    evaluation = evaluator.evaluate_action(action=event)
    bdd_context["evaluation"] = evaluation


@then(parsers.parse('the Evaluator Node rejects the draft with validation error "{error_msg}"'))
def step_evaluator_rejects(bdd_context: dict[str, Any], error_msg: str) -> None:
    evaluation = bdd_context["evaluation"]
    assert evaluation.valid is False
    assert error_msg in evaluation.critique


@then("ALOS routes back to Planner to self-correct the execution plan")
def step_routes_back_to_planner(bdd_context: dict[str, Any]) -> None:
    evaluation = bdd_context["evaluation"]
    assert evaluation.valid is False


@then(parsers.parse('the Evaluator Node approves the plan with status "{status}"'))
def step_evaluator_approves(bdd_context: dict[str, Any], status: str) -> None:
    evaluation = bdd_context["evaluation"]
    assert evaluation.valid is True
    assert evaluation.critique == status
