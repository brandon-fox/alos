"""ALOS State Graph — Dual-Loop Reasoning Orchestrator.

Spec: specs/007-dual-loop-reasoning/plan.md, specs/031-runtime-observability-monitoring/spec.md
Constitution: Article I §1, Article II §3, Article III §1
"""

from __future__ import annotations

from typing import Any

from alos.core.config import ALOSConfig
from alos.core.context_assembler import ContextAssembler, ContextPayload
from alos.core.evaluator import EvaluatorNode
from alos.core.planner import PlannerNode
from alos.core.protocols import (
    AuditLoggerProtocol,
    DecisionLoggerProtocol,
    MCPGatewayProtocol,
    TelemetryProtocol,
)
from alos.integrations.mcp_gateway import MCPGateway
from alos.logs.decision_log import DecisionLogger
from alos.logs.system_audit import SystemAuditLogger
from alos.logs.telemetry import TelemetryTracer, global_tracer
from alos.schemas.actions import BaseAction


def _default_tracer(config: ALOSConfig) -> TelemetryProtocol:
    if config.telemetry_log_path or not config.telemetry_enabled:
        return TelemetryTracer(
            log_file_path=config.telemetry_log_path, enabled=config.telemetry_enabled
        )
    return global_tracer


class ALOSStateGraph:
    """State graph engine connecting all five ALOS layers with hierarchical observability."""

    MAX_SELF_CORRECTION_ATTEMPTS = 5

    def __init__(
        self,
        vault_dir: str | None = None,
        audit_log_path: str | None = None,
        decision_log_path: str | None = None,
        mcp_gateway: MCPGatewayProtocol | None = None,
        audit_logger: AuditLoggerProtocol | None = None,
        decision_logger: DecisionLoggerProtocol | None = None,
        config: ALOSConfig | None = None,
        tracer: TelemetryProtocol | None = None,
    ) -> None:
        self.config = config or ALOSConfig()
        self.tracer: TelemetryProtocol = (
            tracer if tracer is not None else _default_tracer(self.config)
        )
        self.vault_dir = vault_dir or self.config.vault_dir
        self.context_assembler = ContextAssembler(vault_dir=self.vault_dir)
        self.mcp_gateway: MCPGatewayProtocol = (
            mcp_gateway
            if mcp_gateway is not None
            else MCPGateway(mock_mode=self.config.mock_mode, tracer=self.tracer)
        )
        self.audit_logger: AuditLoggerProtocol = (
            audit_logger
            if audit_logger is not None
            else SystemAuditLogger(log_file_path=audit_log_path or self.config.audit_log_path)
        )
        self.decision_logger: DecisionLoggerProtocol = (
            decision_logger
            if decision_logger is not None
            else DecisionLogger(log_file_path=decision_log_path or self.config.decision_log_path)
        )

    def _record_rejection(
        self, draft: BaseAction, critique: str, rounds: int, alternatives: list[str]
    ) -> None:
        alternatives.append(
            f"{draft.action_type} at {getattr(draft, 'start_time', 'N/A')} — REJECTED: {critique}"
        )
        self.tracer.inc_counter("alos_self_correction_rounds_total")
        self.audit_logger.log_event(
            step="Evaluator Check",
            status="REJECTED",
            reason=critique,
            metadata={"attempt": rounds, "action": draft.action_type},
        )

    def _run_reasoning_loop(
        self, user_query: str, context: ContextPayload
    ) -> tuple[BaseAction | None, int]:
        planner = PlannerNode(context=context)
        evaluator = EvaluatorNode(
            context=context,
            decision_logger=self.decision_logger,
            trigger=user_query,
            tracer=self.tracer,
        )
        critique: str | None = None
        rounds = 0
        alternatives: list[str] = []

        while rounds < self.MAX_SELF_CORRECTION_ATTEMPTS:
            with self.tracer.span("planner.draft", tags={"attempt": rounds + 1}):
                draft = planner.generate_draft_action(user_query, critique_feedback=critique)
                tokens = float(max(1, len(user_query.split()) * 4))
                self.tracer.inc_counter(
                    "alos_tokens_consumed_total", amount=tokens, labels={"component": "planner"}
                )
            with self.tracer.span("evaluator.evaluate", tags={"action": draft.action_type}):
                res = evaluator.evaluate_action(draft, list(alternatives), rounds)
            if res.valid:
                self.audit_logger.log_event(
                    step="Evaluator Check",
                    status="APPROVED",
                    metadata={
                        "action": draft.action_type,
                        "risk_level": res.risk_level.value,
                        "self_correction_rounds": rounds,
                    },
                )
                return draft, rounds
            rounds += 1
            critique = res.critique
            self._record_rejection(draft, critique, rounds, alternatives)
        return None, rounds

    def _execute_approved(self, action: BaseAction, rounds: int) -> dict[str, Any]:
        with self.tracer.span("mcp.execute", tags={"action": action.action_type}):
            exec_resp = self.mcp_gateway.execute_tool(action.action_type, action.model_dump())
            self.audit_logger.log_event(
                step="MCP Execution",
                status=exec_resp.get("status", "SUCCESS"),
                metadata=exec_resp,
            )
        return {
            "status": "SUCCESS",
            "final_action": action.model_dump(),
            "self_correction_attempts": rounds,
            "execution_response": exec_resp,
        }

    def run(self, user_query: str) -> dict[str, Any]:
        """Execute dual-loop reasoning state graph with end-to-end span tracing."""
        with self.tracer.span("state_graph.run", tags={"query_length": len(user_query)}) as root:
            with self.tracer.span("context.assemble"):
                context = self.context_assembler.assemble_context(user_query)
                self.audit_logger.log_event(
                    step="Context Assembly",
                    status="SUCCESS",
                    metadata={
                        "preferences_count": len(context.preferences),
                        "corrections_count": len(context.corrections),
                    },
                )
            final_action, rounds = self._run_reasoning_loop(user_query, context)
            if final_action is None:
                self.audit_logger.log_event(
                    step="State Graph",
                    status="FAILED",
                    reason="Max self-correction attempts exceeded",
                    metadata={"max_attempts": self.MAX_SELF_CORRECTION_ATTEMPTS},
                )
                res: dict[str, Any] = {
                    "status": "FAILED",
                    "reason": "Max self-correction attempts reached without valid plan",
                    "self_correction_attempts": rounds,
                }
            else:
                res = self._execute_approved(final_action, rounds)
            self.tracer.inc_counter("alos_agent_runs_total", labels={"status": res["status"]})
            res["trace_id"] = root.trace_id
        if getattr(root, "duration_ms", None) is not None:
            self.tracer.observe_histogram(
                "alos_agent_run_duration_ms",
                float(root.duration_ms),
                labels={"status": res["status"]},
            )
        return res
