"""Model Context Protocol (MCP) gateway and tool execution handlers."""

import uuid
from typing import Any

import mcp.types as mcp_types

from alos.core.protocols import MCPGatewayProtocol, ToolHandlerProtocol


class TodoistTaskHandler:
    """Handler for Todoist task creation (SOLID: SRP)."""

    def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute Todoist task creation with provided payload."""
        task_id = str(uuid.uuid4())[:8]
        return {
            "status": "SUCCESS",
            "tool": "todoist_create_task",
            "task_id": task_id,
            "title": payload.get("title"),
            "due_date": payload.get("due_date"),
        }


class GoogleCalendarListHandler:
    """Handler for listing Google Calendar events (SOLID: SRP)."""

    def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute Google Calendar event listing for specified date."""
        return {
            "status": "SUCCESS",
            "tool": "google_calendar_list_events",
            "date": payload.get("date"),
            "events": [
                {"title": "Morning Standup", "start_time": "09:30:00", "end_time": "10:00:00"},
                {"title": "Focus Block", "start_time": "14:00:00", "end_time": "16:00:00"},
            ],
        }


class GoogleCalendarCreateHandler:
    """Handler for Google Calendar event creation (SOLID: SRP)."""

    def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute Google Calendar event creation with start and end times."""
        return {
            "status": "SUCCESS",
            "tool": "google_calendar_create_event",
            "event_id": str(uuid.uuid4())[:8],
            "title": payload.get("title"),
            "start_time": payload.get("start_time"),
            "end_time": payload.get("end_time"),
        }


class EmailDraftHandler:
    """Handler for draft email creation (SOLID: SRP)."""

    def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute draft email creation with recipient and subject."""
        return {
            "status": "SUCCESS",
            "tool": "email_create_draft",
            "draft_id": str(uuid.uuid4())[:8],
            "to": payload.get("to_email"),
            "subject": payload.get("subject"),
        }


class WebSearchHandler:
    """Handler for web search queries (SOLID: SRP)."""

    def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute web search query and return formatted search results."""
        return {
            "status": "SUCCESS",
            "tool": "web_search",
            "query": payload.get("query"),
            "results": [
                {"title": "Result 1", "snippet": "Sample search response for query"},
            ],
        }


class MCPGateway(MCPGatewayProtocol):
    """Model Context Protocol (MCP) Gateway for Workspace & Tool integrations.

    Integrates official Anthropic mcp SDK types (mcp.types) and implements OCP by maintaining an
    extensible tool handler registry and DIP by conforming to MCPGatewayProtocol.
    """

    def __init__(self, mock_mode: bool = True):
        self.mock_mode = mock_mode
        self._handlers: dict[str, ToolHandlerProtocol] = {}
        self._mcp_tools: dict[str, Any] = {}
        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        """Register default set of tool handlers."""
        self.register_handler("todoist_create_task", TodoistTaskHandler())
        self.register_handler("google_calendar_list_events", GoogleCalendarListHandler())
        self.register_handler("google_calendar_create_event", GoogleCalendarCreateHandler())
        self.register_handler("email_create_draft", EmailDraftHandler())
        self.register_handler("web_search", WebSearchHandler())

    def register_handler(self, tool_name: str, handler: ToolHandlerProtocol) -> None:
        """Register a new tool handler without modifying gateway dispatch logic (SOLID: OCP)."""
        self._handlers[tool_name] = handler
        # Register standard MCP Tool schema representation
        self._mcp_tools[tool_name] = mcp_types.Tool(
            name=tool_name,
            description=f"ALOS Integration Tool for {tool_name}",
            inputSchema={"type": "object"},
        )

    def execute_tool(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Dispatch tool execution via registered tool handler strategy."""
        handler = self._handlers.get(tool_name)
        if handler:
            return handler.execute(payload)
        return {
            "status": "UNKNOWN_TOOL",
            "tool": tool_name,
            "payload": payload,
        }
