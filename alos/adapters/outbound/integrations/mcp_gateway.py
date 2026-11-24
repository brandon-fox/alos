"""Ring 3 driven MCP gateway adapter and extensible OCP tool handler registry."""

from __future__ import annotations

from typing import Any

import mcp.types as mt

import alos.integrations.mcp_gateway as _gw
from alos.application.ports.outbound import MCPGatewayPort, TelemetryPort
from alos.core.protocols import ToolHandlerProtocol
from alos.logs.telemetry import global_tracer

_M = dict[str, Any]
_FACS: tuple[tuple[str, type[ToolHandlerProtocol]], ...] = (
    ("todoist_create_task", _gw.TodoistTaskHandler),
    ("google_calendar_list_events", _gw.GoogleCalendarListHandler),
    ("google_calendar_create_event", _gw.GoogleCalendarCreateHandler),
    ("email_create_draft", _gw.EmailDraftHandler),
    ("web_search", _gw.WebSearchHandler),
)


class ToolHandlerRegistry:
    """Open-Closed registry mapping MCP tool names to ToolHandlerProtocol strategies."""

    def __init__(self) -> None:
        self.handlers: dict[str, ToolHandlerProtocol] = {}
        self.tools: dict[str, Any] = {}

    def register(self, name: str, handler: ToolHandlerProtocol) -> None:
        """Register a named tool handler and its MCP Tool schema descriptor."""
        self.handlers[name] = handler
        self.tools[name] = mt.Tool(
            name=name, description=f"ALOS {name}", input_schema={"type": "object"}
        )

    def get(self, name: str) -> ToolHandlerProtocol | None:
        """Return registered ToolHandlerProtocol for name, or None."""
        return self.handlers.get(name)

    def list_tools(self) -> list[Any]:
        """Return all registered MCP Tool descriptors."""
        return list(self.tools.values())

    @classmethod
    def default(cls) -> ToolHandlerRegistry:
        """Build a registry pre-populated with default workspace tool handlers."""
        reg = cls()
        for k, fac in _FACS:
            reg.register(k, fac())
        return reg


class MCPGatewayAdapter(MCPGatewayPort):
    """Driven MCPGatewayPort adapter dispatching registered tool handlers with telemetry."""

    def __init__(
        self,
        mock_mode: bool = True,
        tracer: TelemetryPort | None = None,
        registry: ToolHandlerRegistry | None = None,
    ) -> None:
        self.mock_mode = mock_mode
        self.tracer: TelemetryPort = tracer if tracer is not None else global_tracer
        self.registry = registry or ToolHandlerRegistry.default()

    def register_handler(self, tool_name: str, handler: ToolHandlerProtocol) -> None:
        """Register an additional tool handler on the underlying registry."""
        self.registry.register(tool_name, handler)

    def execute_tool(self, tool_name: str, payload: _M) -> _M:
        """Execute a named MCP tool handler and emit span/counter/histogram telemetry."""
        t = {"tool": tool_name}
        with self.tracer.span(f"mcp.tool.{tool_name}", tags=t) as sp:
            h = self.registry.get(tool_name)
            r = h.execute(payload) if h else {"status": "UNKNOWN_TOOL", **t, "payload": payload}
        lbl = {**t, "status": str(r.get("status", "SUCCESS"))}
        self.tracer.inc_counter("alos_mcp_tool_calls_total", labels=lbl)
        if getattr(sp, "duration_ms", None) is not None:
            self.tracer.observe_histogram("alos_mcp_tool_duration_ms", float(sp.duration_ms), t)
        return r
