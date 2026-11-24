"""Ring 1 pure domain action schemas and Literal-discriminated union (ADR-0022, FR-3603)."""

from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field


class BaseAction(BaseModel):
    """Immutable base Pydantic model for all ALOS actions."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    action_type: str = Field(..., description="Action type identifier")
    description: str = Field(..., description="Human readable description")


class TodoistTaskCreate(BaseAction):
    """Immutable action schema for creating tasks in Todoist."""

    action_type: Literal["todoist_create_task"] = "todoist_create_task"
    description: str = "Create task in Todoist"
    title: str
    due_date: str | None = None
    priority: int = 1
    labels: list[str] = Field(default_factory=list)


class GoogleCalendarEvent(BaseAction):
    """Immutable action schema for creating Google Calendar events."""

    action_type: Literal["google_calendar_create_event"] = "google_calendar_create_event"
    description: str = "Create Google Calendar Event"
    title: str
    start_time: str
    end_time: str
    attendees: list[str] = Field(default_factory=list)


class EmailDraft(BaseAction):
    """Immutable action schema for creating draft emails (Safety Matrix: HIGH)."""

    action_type: Literal["email_create_draft"] = "email_create_draft"
    description: str = "Create draft email"
    to_email: str
    subject: str
    body: str


class EmailSend(BaseAction):
    """Immutable action schema for sending external emails (Safety Matrix: HIGH)."""

    action_type: Literal["email_send"] = "email_send"
    description: str = "Send external email"
    to_email: str
    subject: str
    body: str


class VaultNoteUpdate(BaseAction):
    """Immutable action schema for updating or creating Obsidian vault notes."""

    action_type: Literal["vault_update_note"] = "vault_update_note"
    description: str = "Update or create Markdown vault note"
    filename: str
    content: str


class WebSearchQuery(BaseAction):
    """Immutable action schema for executing web search queries."""

    action_type: Literal["web_search"] = "web_search"
    description: str = "Execute multi-source web search"
    query: str


ActionUnion: TypeAlias = Annotated[
    TodoistTaskCreate
    | GoogleCalendarEvent
    | EmailDraft
    | EmailSend
    | VaultNoteUpdate
    | WebSearchQuery,
    Field(discriminator="action_type"),
]


class ActionPlan(BaseModel):
    """Immutable container model for an ordered plan of discriminated execution actions."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    plan_id: str
    goal: str
    actions: list[ActionUnion] = Field(default_factory=list)
    risk_level: str = "LOW"
