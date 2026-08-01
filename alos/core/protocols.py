from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class MemoryStoreProtocol(Protocol):
    """Protocol for vector and spec-aware memory stores (SOLID: ISP)."""

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        ...


@runtime_checkable
class AuditLoggerProtocol(Protocol):
    """Protocol for append-only system audit logging (SOLID: ISP & DIP)."""

    def log_event(
        self,
        step: str,
        status: str,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ...


@runtime_checkable
class DecisionLoggerProtocol(Protocol):
    """Protocol for architectural decision record (ADR) logging (SOLID: ISP & DIP)."""

    def log_decision(
        self,
        trigger: str,
        action: Any,
        risk_level: Any,
        decision: str,
        rationale: str,
        constitution_articles_checked: list[str],
        preferences_checked: list[str],
        corrections_checked: list[str],
        alternatives_considered: list[str],
        self_correction_rounds: int,
    ) -> dict[str, Any]:
        ...


@runtime_checkable
class ToolHandlerProtocol(Protocol):
    """Protocol for discrete MCP tool execution handlers (SOLID: SRP & OCP)."""

    def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        ...


@runtime_checkable
class MCPGatewayProtocol(Protocol):
    """Protocol for MCP gateway integrations (SOLID: ISP & DIP)."""

    def execute_tool(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        ...
