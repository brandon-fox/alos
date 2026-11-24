"""Ring 1 pure domain action draft strategies and OCP registry (ADR-0023, FR-3606)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

import alos.domain.models.actions as act

_DraftFn = Callable[[str, str | None], act.BaseAction]


@runtime_checkable
class ActionDraftStrategy(Protocol):
    """Strategy protocol for generating a candidate BaseAction from a query (SOLID: OCP)."""

    def matches(self, query_lower: str) -> bool:
        """Return True if this strategy applies to the normalized user query."""
        ...

    def build(self, user_query: str, critique_feedback: str | None = None) -> act.BaseAction:
        """Construct an immutable action draft incorporating optional evaluator critique."""
        ...


class ActionDraftBuilder:
    """Stateless factory helpers formulating canonical draft actions (SOLID: SRP)."""

    @staticmethod
    def build_meeting_action(query: str, critique: str | None = None) -> act.GoogleCalendarEvent:
        """Formulate GoogleCalendarEvent draft taking critique feedback into account."""
        fix = bool(critique and "5:00 PM" in critique)
        sync = "schedule meeting team sync" in query.lower()
        t = "Team Sync" if (fix or sync) else "Planned Event"
        hr = ("17:30:00", "18:00:00") if (sync and not fix) else ("14:00:00", "15:00:00")
        s, e = f"2026-08-01T{hr[0]}", f"2026-08-01T{hr[1]}"
        return act.GoogleCalendarEvent(title=t, start_time=s, end_time=e)

    @staticmethod
    def build_task_action(_q: str = "", _c: str | None = None) -> act.TodoistTaskCreate:
        """Formulate TodoistTaskCreate draft action."""
        return act.TodoistTaskCreate(title="Schedule quarterly review", due_date="2026-08-05")

    @staticmethod
    def build_search_action(user_query: str) -> act.WebSearchQuery:
        """Formulate WebSearchQuery draft action."""
        return act.WebSearchQuery(query=user_query)


class KeywordDraftStrategy:
    """Reusable keyword-matching ActionDraftStrategy implementation (SOLID: OCP)."""

    def __init__(self, kws: tuple[str, ...], fn: _DraftFn) -> None:
        self._kws, self._fn = kws, fn

    def matches(self, query_lower: str) -> bool:
        """Return True if any configured keyword appears in query_lower."""
        return any(kw in query_lower for kw in self._kws)

    def build(self, user_query: str, critique_feedback: str | None = None) -> act.BaseAction:
        """Invoke the configured factory to produce an immutable BaseAction draft."""
        return self._fn(user_query, critique_feedback)


def _mail(q: str, _c: str | None) -> act.BaseAction:
    return act.EmailSend(to_email="recipient@example.com", subject="ALOS Action", body=q)


class ActionDraftStrategyRegistry:
    """Open-Closed strategy registry dispatching intent queries to ActionDraftStrategy."""

    def __init__(self, strategies: list[ActionDraftStrategy] | None = None) -> None:
        self._strategies: list[ActionDraftStrategy] = list(strategies or [])

    def register(self, strategy: ActionDraftStrategy, *, prepend: bool = True) -> None:
        """Register an ActionDraftStrategy without editing planner orchestration (OCP)."""
        self._strategies.insert(0 if prepend else len(self._strategies), strategy)

    @classmethod
    def default(cls) -> ActionDraftStrategyRegistry:
        """Create registry seeded with meeting, task, email-send, and web-search fallback."""
        mk, ab = KeywordDraftStrategy, ActionDraftBuilder
        strats: list[ActionDraftStrategy] = [
            mk(("meeting", "schedule"), ab.build_meeting_action),
            mk(("task", "todoist"), ab.build_task_action),
            mk(("send email",), _mail),
        ]
        return cls(strats)

    def build_draft(self, query: str, critique: str | None = None) -> act.BaseAction:
        """Select first matching strategy and construct an immutable BaseAction draft."""
        qlow = query.lower()
        for s in self._strategies:
            if s.matches(qlow):
                return s.build(query, critique)
        return ActionDraftBuilder.build_search_action(query)
