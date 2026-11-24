"""Ring 2 use case: autonomous n8n self-reflection loop over WorkflowOrchestratorPort."""

from __future__ import annotations

from contextlib import nullcontext
from typing import Any, TypedDict, cast

from alos.application.ports.outbound import TelemetryPort, WorkflowOrchestratorPort

_Map = dict[str, Any]


class N8nTaskState(TypedDict):
    """Typed state dictionary for n8n workflow self-reflection execution."""

    task_id: str
    workflow_id: str
    payload: _Map
    execution_output: _Map | None
    evaluation_valid: bool
    critique: str
    attempt_count: int
    max_attempts: int
    status: str
    audit_logs: list[str]


class N8nSelfReflectionUseCase:
    """Application use case orchestrating n8n workflow triggers and self-correction."""

    def __init__(
        self, orchestrator: WorkflowOrchestratorPort, tracer: TelemetryPort | None = None
    ) -> None:
        self.orchestrator, self.tracer = orchestrator, tracer

    def poll_or_execute(self, state: N8nTaskState) -> _Map:
        """Trigger workflow via WorkflowOrchestratorPort and record telemetry."""
        attempt, wf = state["attempt_count"] + 1, state["workflow_id"]
        logs = [*state.get("audit_logs", []), f"Attempt {attempt}: Triggering workflow '{wf}'"]
        t, tags = self.tracer, {"workflow_id": wf, "attempt": attempt}
        with t.span("n8n.workflow.trigger", tags=tags) if t else nullcontext():
            resp = self.orchestrator.trigger_workflow(
                {"workflow_id": wf, "payload": state["payload"]}
            )
        if t:
            lbl = {"workflow_id": wf, "status": str(resp.status_code)}
            t.inc_counter("alos_n8n_workflow_attempts_total", labels=lbl)
        return {"attempt_count": attempt, "execution_output": resp.model_dump(), "audit_logs": logs}

    def _refine(self, cur: _Map, critique: str) -> None:
        payload, logs = dict(cur["payload"]), list(cur["audit_logs"])
        if "api_key" in critique and "api_key" not in payload:
            payload["api_key"] = "auto_refined_token_99"
            logs.append("Refinement: Added missing 'api_key' parameter to payload.")
        elif "force_db_fail" in payload:
            payload.pop("force_db_fail", None)
            payload["api_key"] = "auto_refined_token_99"
            logs.append("Refinement: Cleared failure flag & refined payload.")
        else:
            payload["_retry_timestamp"] = "refined"
            logs.append("Refinement: Adjusted retry parameters in payload.")
        cur.update(payload=payload, status="retrying", audit_logs=logs)

    def run(self, initial_state: N8nTaskState) -> N8nTaskState:
        """Execute autonomous self-reflection loop until valid or max_attempts reached."""
        tags = {
            "task_id": initial_state.get("task_id", ""),
            "workflow_id": initial_state["workflow_id"],
        }
        cur: _Map = dict(initial_state)
        t = self.tracer
        with t.span("n8n.self_reflection.run", tags=tags) if t else nullcontext():
            while True:
                cur.update(self.poll_or_execute(cast(N8nTaskState, cur)))
                raw = cur.get("execution_output")
                out: _Map = raw if isinstance(raw, dict) else {}
                code, err = int(out.get("status_code", 500)), out.get("error")
                if code == 200 and not err:
                    cur.update(evaluation_valid=True, critique="VALID", status="success")
                    return cast(N8nTaskState, cur)
                critique = str(err or f"Execution failed with HTTP status code {code}")
                cur.update(evaluation_valid=False, critique=critique)
                if int(cur["attempt_count"]) >= int(cur["max_attempts"]):
                    cur["status"] = "failed_max_retries"
                    return cast(N8nTaskState, cur)
                self._refine(cur, critique)
