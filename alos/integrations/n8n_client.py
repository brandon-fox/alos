"""Integration client for n8n API workflows and webhook triggers."""

from dataclasses import dataclass, field
from typing import Any

from alos.core.config import ALOSConfig


@dataclass
class N8nExecutionResponse:
    """Response object returned by N8nClient execution or polling operations."""

    status_code: int
    data: dict[str, Any] = field(default_factory=dict)
    execution_id: str | None = None
    error: str | None = None


class N8nClient:
    """Client for triggering and polling n8n automation workflows."""

    def __init__(
        self,
        base_url: str = "http://localhost:5678",
        api_key: str | None = None,
        mock_mode: bool | None = None,
    ) -> None:
        config = ALOSConfig()
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.mock_mode = config.mock_mode if mock_mode is None else mock_mode

    def trigger_workflow(self, workflow_id: str, payload: dict[str, Any]) -> N8nExecutionResponse:
        """Trigger an n8n workflow or webhook endpoint.

        Args:
            workflow_id: Target workflow or webhook identifier.
            payload: Input payload parameters for the workflow.

        Returns:
            N8nExecutionResponse containing status code, execution data, or error message.
        """
        if self.mock_mode:
            return self._mock_trigger(workflow_id, payload)

        # Production execution placeholder (e.g. httpx.post)
        return N8nExecutionResponse(
            status_code=200,
            data={"status": "ok", "workflow_id": workflow_id, "output": payload},
            execution_id=f"exec-{workflow_id}-001",
        )

    def _mock_trigger(self, workflow_id: str, payload: dict[str, Any]) -> N8nExecutionResponse:
        """Simulate workflow execution for mock mode testing."""
        if payload.get("force_fail"):
            return N8nExecutionResponse(
                status_code=500,
                data={},
                error="Internal Workflow Error: Execution force failed.",
            )

        if "api_key" not in payload:
            return N8nExecutionResponse(
                status_code=400,
                data={},
                error="Validation Error: Missing required parameter 'api_key'.",
            )

        return N8nExecutionResponse(
            status_code=200,
            data={
                "status": "ok",
                "workflow_id": workflow_id,
                "items_processed": 5,
                "result": "Task completed successfully",
            },
            execution_id=f"mock-exec-{workflow_id}",
        )
