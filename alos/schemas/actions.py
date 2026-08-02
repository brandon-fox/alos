"""Action schema definitions for ALOS execution planning and tool dispatch."""

from pydantic import BaseModel, Field


class BaseAction(BaseModel):
    """Base Pydantic model for all ALOS actions."""

    action_type: str = Field(..., description="Action type identifier")
    description: str = Field(..., description="Human readable description")


class TodoistTaskCreate(BaseAction):
    """Action schema for creating tasks in Todoist."""

    action_type: str = "todoist_create_task"
    description: str = "Create task in Todoist"
    title: str
    due_date: str | None = None
    priority: int = 1
    labels: list[str] = Field(default_factory=list)


class GoogleCalendarEvent(BaseAction):
    """Action schema for creating Google Calendar events."""

    action_type: str = "google_calendar_create_event"
    description: str = "Create Google Calendar Event"
    title: str
    start_time: str
    end_time: str
    attendees: list[str] = Field(default_factory=list)


class EmailDraft(BaseAction):
    """Action schema for creating draft emails."""

    action_type: str = "email_create_draft"
    description: str = "Create draft email"
    to_email: str
    subject: str
    body: str


class VaultNoteUpdate(BaseAction):
    """Action schema for updating or creating Obsidian vault notes."""

    action_type: str = "vault_update_note"
    description: str = "Update or create Markdown vault note"
    filename: str
    content: str


class WebSearchQuery(BaseAction):
    """Action schema for executing web search queries."""

    action_type: str = "web_search"
    description: str = "Execute multi-source web search"
    query: str


class ActionPlan(BaseModel):
    """Container model for an ordered plan of execution actions."""

    plan_id: str
    goal: str
    actions: list[BaseAction] = Field(default_factory=list)
    risk_level: str = "LOW"
