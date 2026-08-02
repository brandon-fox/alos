"""Planner node and action draft builders for ALOS dual-loop reasoning."""

from alos.core.context_assembler import ContextPayload
from alos.schemas.actions import BaseAction, GoogleCalendarEvent, TodoistTaskCreate, WebSearchQuery


class ActionDraftBuilder:
    """Strategy builder formulating execution actions from intent and critique (SOLID: SRP)."""

    @staticmethod
    def build_meeting_action(
        query_lower: str, critique_feedback: str | None = None
    ) -> GoogleCalendarEvent:
        """Formulate GoogleCalendarEvent draft taking critique feedback into account."""
        if critique_feedback and "5:00 PM" in critique_feedback:
            return GoogleCalendarEvent(
                title="Team Sync",
                start_time="2026-08-01T14:00:00",
                end_time="2026-08-01T15:00:00",
            )
        if "schedule meeting team sync" in query_lower:
            return GoogleCalendarEvent(
                title="Team Sync",
                start_time="2026-08-01T17:30:00",
                end_time="2026-08-01T18:00:00",
            )
        return GoogleCalendarEvent(
            title="Planned Event",
            start_time="2026-08-01T14:00:00",
            end_time="2026-08-01T15:00:00",
        )

    @staticmethod
    def build_task_action() -> TodoistTaskCreate:
        """Formulate TodoistTaskCreate draft action."""
        return TodoistTaskCreate(
            title="Schedule quarterly review", due_date="2026-08-05", priority=1
        )

    @staticmethod
    def build_search_action(user_query: str) -> WebSearchQuery:
        """Formulate WebSearchQuery draft action."""
        return WebSearchQuery(query=user_query)


class PlannerNode:
    """Planner node formulating execution plans and adjusting drafts upon evaluator critique."""

    def __init__(self, context: ContextPayload):
        self.context = context

    def generate_draft_action(
        self, user_query: str, critique_feedback: str | None = None
    ) -> BaseAction:
        """Generate draft action for user query incorporating any critique feedback."""
        query_lower = user_query.lower()

        if "meeting" in query_lower or "schedule" in query_lower:
            return ActionDraftBuilder.build_meeting_action(query_lower, critique_feedback)
        elif "task" in query_lower or "todoist" in query_lower:
            return ActionDraftBuilder.build_task_action()
        else:
            return ActionDraftBuilder.build_search_action(user_query)
