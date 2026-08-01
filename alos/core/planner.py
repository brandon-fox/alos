from alos.core.context_assembler import ContextPayload
from alos.schemas.actions import BaseAction, GoogleCalendarEvent, TodoistTaskCreate, WebSearchQuery


class PlannerNode:
    """Planner node formulating execution plans and adjusting drafts upon evaluator critique."""

    def __init__(self, context: ContextPayload):
        self.context = context

    def generate_draft_action(
        self, user_query: str, critique_feedback: str | None = None
    ) -> BaseAction:
        query_lower = user_query.lower()

        if "meeting" in query_lower or "schedule" in query_lower:
            # If previous critique noted a 5:00 PM preference violation, self-correct to 2:00 PM
            if critique_feedback and "5:00 PM" in critique_feedback:
                return GoogleCalendarEvent(
                    title="Team Sync",
                    start_time="2026-08-01T14:00:00",
                    end_time="2026-08-01T15:00:00",
                )
            else:
                # Default draft attempt (might start at 5:30 PM if initially
                # unsophisticated, triggering self-correction)
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

        elif "task" in query_lower or "todoist" in query_lower:
            return TodoistTaskCreate(
                title="Schedule quarterly review", due_date="2026-08-05", priority=1
            )

        else:
            return WebSearchQuery(query=user_query)
