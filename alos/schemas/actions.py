"""Strangler-Fig shim for legacy alos.schemas.actions imports (Spec 036 FR-3611, ADR-0024)."""

# Strangler-Fig shim: delegate canonical action models to Ring 1 (alos.domain.models.actions).
from alos.domain.models.actions import (
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
