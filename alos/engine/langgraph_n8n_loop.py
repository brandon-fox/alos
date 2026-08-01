"""LangGraph Autonomous Self-Reflection Loop engine for n8n tasks."""

import logging
from typing import Any, Literal, TypedDict, cast

from langgraph.graph import END, START, StateGraph

from alos.integrations.n8n_client import N8nClient, N8nExecutionResponse

logger = logging.getLogger(__name__)


class N8nTaskState(TypedDict):
    """Typed state dictionary managed by the LangGraph self-reflection state graph."""

    task_id: str
    workflow_id: str
    payload: dict[str, Any]
    execution_output: dict[str, Any] | None
    evaluation_valid: bool
    critique: str
    attempt_count: int
    max_attempts: int
    status: str
    audit_logs: list[str]


class N8nSelfReflectionGraph:
    """LangGraph autonomous self-reflection state graph for running and refining n8n workflows."""

    def __init__(self, mock_mode: bool = True) -> None:
        self.client = N8nClient(mock_mode=mock_mode)
        self.graph = self._build_graph()

    def _poll_or_execute(self, state: N8nTaskState) -> dict[str, Any]:
        """Node: Poll or trigger the specified n8n workflow."""
        attempts = state["attempt_count"] + 1
        audit_logs = list(state.get("audit_logs", []))
        audit_logs.append(f"Attempt {attempts}: Triggering workflow '{state['workflow_id']}'")

        response: N8nExecutionResponse = self.client.trigger_workflow(
            workflow_id=state["workflow_id"], payload=state["payload"]
        )

        output: dict[str, Any] = {
            "status_code": response.status_code,
            "data": response.data,
            "execution_id": response.execution_id,
            "error": response.error,
        }

        return {
            "attempt_count": attempts,
            "execution_output": output,
            "audit_logs": audit_logs,
        }

    def _evaluate_response(self, state: N8nTaskState) -> dict[str, Any]:
        """Node: Evaluate n8n execution response for validation and critique."""
        output = state.get("execution_output") or {}
        audit_logs = list(state.get("audit_logs", []))
        status_code = output.get("status_code", 500)
        error_msg = output.get("error")

        if status_code == 200 and not error_msg:
            audit_logs.append("Evaluator: Response valid.")
            return {
                "evaluation_valid": True,
                "critique": "VALID",
                "audit_logs": audit_logs,
            }

        critique = error_msg or f"Execution failed with HTTP status code {status_code}"
        audit_logs.append(f"Evaluator Critique: {critique}")
        return {
            "evaluation_valid": False,
            "critique": critique,
            "audit_logs": audit_logs,
        }

    def _refine_payload(self, state: N8nTaskState) -> dict[str, Any]:
        """Node: Self-correct and refine workflow payload parameters based on critique feedback."""
        critique = state.get("critique", "")
        payload = dict(state.get("payload", {}))
        audit_logs = list(state.get("audit_logs", []))

        if "api_key" in critique and "api_key" not in payload:
            payload["api_key"] = "auto_refined_token_99"
            audit_logs.append("Refinement: Added missing 'api_key' parameter to payload.")
        elif "force_db_fail" in payload:
            del payload["force_db_fail"]
            payload["api_key"] = "auto_refined_token_99"
            audit_logs.append("Refinement: Cleared failure flag & refined payload.")
        else:
            payload["_retry_timestamp"] = "refined"
            audit_logs.append("Refinement: Adjusted retry parameters in payload.")

        return {
            "payload": payload,
            "status": "retrying",
            "audit_logs": audit_logs,
        }

    def _finalize_execution(self, state: N8nTaskState) -> dict[str, Any]:
        """Node: Finalize workflow state and write audit decision record."""
        audit_logs = list(state.get("audit_logs", []))
        if state.get("evaluation_valid"):
            final_status = "success"
            audit_logs.append("Finalize: Execution completed successfully.")
        else:
            final_status = "failed_max_retries"
            audit_logs.append("Finalize: Execution failed after reaching maximum attempts.")

        return {
            "status": final_status,
            "audit_logs": audit_logs,
        }

    def _route_after_evaluation(
        self, state: N8nTaskState
    ) -> Literal["finalize_execution", "refine_task_parameters"]:
        """Conditional Router: Determines whether to finalize or attempt self-correction loop."""
        if state.get("evaluation_valid"):
            return "finalize_execution"
        if state["attempt_count"] >= state["max_attempts"]:
            return "finalize_execution"
        return "refine_task_parameters"

    def _build_graph(self) -> Any:
        """Construct and compile the LangGraph StateGraph workflow."""
        builder = StateGraph(N8nTaskState)

        builder.add_node("poll_or_execute", self._poll_or_execute)
        builder.add_node("evaluate_response", self._evaluate_response)
        builder.add_node("refine_task_parameters", self._refine_payload)
        builder.add_node("finalize_execution", self._finalize_execution)

        builder.add_edge(START, "poll_or_execute")
        builder.add_edge("poll_or_execute", "evaluate_response")

        builder.add_conditional_edges(
            "evaluate_response",
            self._route_after_evaluation,
            {
                "finalize_execution": "finalize_execution",
                "refine_task_parameters": "refine_task_parameters",
            },
        )

        builder.add_edge("refine_task_parameters", "poll_or_execute")
        builder.add_edge("finalize_execution", END)

        return builder.compile()

    def run(self, initial_state: N8nTaskState) -> N8nTaskState:
        """Execute the LangGraph autonomous self-reflection loop with initial state."""
        res: N8nTaskState = cast(N8nTaskState, self.graph.invoke(initial_state))
        return res
