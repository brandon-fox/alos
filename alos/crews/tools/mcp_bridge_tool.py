from typing import Any

from pydantic import BaseModel, Field

from alos.integrations.mcp_gateway import MCPGateway


class MCPGatewayInput(BaseModel):
    tool_name: str = Field(
        ..., description="Name of the MCP tool to execute (e.g. web_search, todoist_create_task)"
    )
    payload: dict[str, Any] = Field(
        default_factory=dict, description="Parameters to pass to the MCP tool"
    )


class MCPGatewayTool:
    """Tool bridging CrewAI tasks to Antigravity / ALOS MCP Gateway."""

    name: str = "mcp_gateway_bridge"
    description: str = "Bridges CrewAI tasks to registered MCP tool handlers."
    args_schema: type[BaseModel] = MCPGatewayInput

    def __init__(self) -> None:
        self.gateway = MCPGateway()

    def run(self, tool_name: str, payload: dict[str, Any] | None = None) -> str:
        params = payload or {}
        res = self.gateway.execute_tool(tool_name, params)
        return str(res)
