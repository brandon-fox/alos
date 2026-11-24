"""Strangler-Fig shim for legacy alos.schemas package imports (Spec 036 FR-3611, ADR-0024)."""

# Strangler-Fig shim: re-export canonical Ring 1 action models via legacy path.
from alos.schemas.actions import (
    ActionPlan,
    ActionUnion,
    BaseAction,
    EmailDraft,
    EmailSend,
    GoogleCalendarEvent,
    TodoistTaskCreate,
    VaultNoteUpdate,
    WebSearchQuery,
)

__all__ = [
    "ActionPlan",
    "ActionUnion",
    "BaseAction",
    "EmailDraft",
    "EmailSend",
    "GoogleCalendarEvent",
    "TodoistTaskCreate",
    "VaultNoteUpdate",
    "WebSearchQuery",
]
