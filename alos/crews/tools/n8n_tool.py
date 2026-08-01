from typing import Any

from pydantic import BaseModel, Field

from alos.integrations.n8n_client import N8nClient


class N8nWorkflowInput(BaseModel):
    workflow_id: str = Field(
        ..., description="Target n8n workflow or webhook ID (e.g. wf-vault-knowledge-ingestion)"
    )
    payload: dict[str, Any] = Field(
        default_factory=dict, description="Input payload data for the workflow"
    )


class N8nWorkflowTool:
    """Tool enabling CrewAI tasks to trigger local n8n workflows."""

    name: str = "n8n_workflow_trigger"
    description: str = "Triggers local n8n automation workflows and webhooks via ALOS N8nClient."
    args_schema: type[BaseModel] = N8nWorkflowInput

    def __init__(self, mock_mode: bool = True) -> None:
        self.client = N8nClient(mock_mode=mock_mode)

    def run(self, workflow_id: str, payload: dict[str, Any] | None = None) -> str:
        params = payload or {}
        res = self.client.trigger_workflow(workflow_id, params)
        if res.error:
            return f"n8n Error ({res.status_code}): {res.error}"
        return f"n8n Success ({res.status_code}): execution_id={res.execution_id}, data={res.data}"
