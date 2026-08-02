"""Safety matrix evaluator tool integration for CrewAI workflows."""

from pydantic import BaseModel, Field

from alos.core.evaluator import EvaluatorNode
from alos.schemas.actions import BaseAction


class ActionEvaluationInput(BaseModel):
    """Input payload model for action safety evaluation."""

    action_type: str = Field(
        ..., description="The type identifier of the action (e.g., email_send, vault_update_note)"
    )
    description: str = Field(..., description="Human-readable description of what the action does")


class SafetyEvaluatorTool:
    """Tool wrapping ALOS Deterministic Safety Matrix Evaluator for CrewAI tasks."""

    name: str = "safety_evaluator"
    description: str = "Evaluates raw action proposed by an agent against the ALOS Safety Matrix."
    args_schema: type[BaseModel] = ActionEvaluationInput

    def __init__(self) -> None:
        self.evaluator = EvaluatorNode()

    def run(self, action_type: str, description: str) -> str:
        """Run safety matrix evaluation for the given action type and description."""
        action = BaseAction(action_type=action_type, description=description)
        result = self.evaluator.evaluate_action(action)

        return (
            f"Evaluation Output:\n"
            f"- Valid: {result.valid}\n"
            f"- Risk Level: {result.risk_level.value}\n"
            f"- Requires Human Approval: {result.requires_approval}\n"
            f"- Critique: {result.critique}"
        )
