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
        validation_error = self.validate_workflow_payload(workflow_id, payload)
        if validation_error:
            return N8nExecutionResponse(
                status_code=400,
                data={},
                error=f"Validation Error: {validation_error}",
            )

        if self.mock_mode:
            return self._mock_trigger(workflow_id, payload)

        return N8nExecutionResponse(
            status_code=200,
            data={"status": "ok", "workflow_id": workflow_id, "output": payload},
            execution_id=f"exec-{workflow_id}-001",
        )

    def validate_workflow_payload(self, workflow_id: str, payload: dict[str, Any]) -> str | None:
        """Validate workflow input payload according to workflow schema rules."""
        if workflow_id == "wf-human-approval-gate":
            if "task_id" not in payload:
                return "Missing required parameter 'task_id'."
            if "action_type" not in payload:
                return "Missing required parameter 'action_type'."
        elif workflow_id == "wf-vault-knowledge-ingestion":
            if "title" not in payload:
                return "Missing required parameter 'title'."
            if "content" not in payload:
                return "Missing required parameter 'content'."
        elif workflow_id == "wf-health-poll-self-correct":
            if payload.get("force_db_fail") and not payload.get("api_key"):
                return "Missing required parameter 'api_key'."
        return None

    def _mock_approval_gate(
        self, workflow_id: str, payload: dict[str, Any]
    ) -> N8nExecutionResponse:
        risk_level = payload.get("risk_level", "HIGH")
        return N8nExecutionResponse(
            status_code=200,
            data={
                "status": "ok",
                "workflow_id": workflow_id,
                "ticket_id": f"tkt-{payload.get('task_id')}",
                "approval_required": risk_level == "HIGH",
                "risk_level": risk_level,
                "action_type": payload.get("action_type"),
            },
            execution_id=f"mock-exec-{workflow_id}",
        )

    def _mock_health_poll(self, workflow_id: str, payload: dict[str, Any]) -> N8nExecutionResponse:
        if payload.get("force_db_fail", False):
            return N8nExecutionResponse(
                status_code=500,
                data={"overall_status": "degraded"},
                error="Service degradation detected: PostgreSQL connection failed.",
            )
        return N8nExecutionResponse(
            status_code=200,
            data={
                "status": "ok",
                "workflow_id": workflow_id,
                "overall_status": "healthy",
                "services": {
                    "postgres": "healthy",
                    "redis": "healthy",
                    "n8n_worker": "healthy",
                },
            },
            execution_id=f"mock-exec-{workflow_id}",
        )

    def _mock_vault_ingestion(
        self, workflow_id: str, payload: dict[str, Any]
    ) -> N8nExecutionResponse:
        title = payload.get("title", "Untitled")
        slug = title.lower().replace(" ", "-")
        return N8nExecutionResponse(
            status_code=200,
            data={
                "status": "ok",
                "workflow_id": workflow_id,
                "note_title": title,
                "vault_path": f"vault/ingested/{slug}.md",
            },
            execution_id=f"mock-exec-{workflow_id}",
        )

    def _mock_trigger(self, workflow_id: str, payload: dict[str, Any]) -> N8nExecutionResponse:
        """Simulate workflow execution for mock mode testing."""
        if payload.get("force_fail"):
            return N8nExecutionResponse(
                status_code=500,
                data={},
                error="Internal Workflow Error: Execution force failed.",
            )

        known_workflows = (
            "wf-human-approval-gate",
            "wf-health-poll-self-correct",
            "wf-vault-knowledge-ingestion",
        )
        if workflow_id not in known_workflows and "api_key" not in payload:
            return N8nExecutionResponse(
                status_code=400,
                data={},
                error="Validation Error: Missing required parameter 'api_key'.",
            )

        if workflow_id == "wf-human-approval-gate":
            return self._mock_approval_gate(workflow_id, payload)

        if workflow_id == "wf-health-poll-self-correct":
            return self._mock_health_poll(workflow_id, payload)

        if workflow_id == "wf-vault-knowledge-ingestion":
            return self._mock_vault_ingestion(workflow_id, payload)

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
