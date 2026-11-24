"""ALOS State Graph — Dual-Loop Reasoning Orchestrator.

Spec: specs/007-dual-loop-reasoning/plan.md, specs/031-runtime-observability-monitoring/spec.md
Constitution: Article I §1, Article II §3, Article III §1
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import alos.application.use_cases as _uc
from alos.application.ports.outbound import HumanApprovalGatePort
from alos.core.config import ALOSConfig
from alos.core.context_assembler import ContextAssembler
from alos.core.protocols import (
    AuditLoggerProtocol,
    DecisionLoggerProtocol,
    MCPGatewayProtocol,
    TelemetryProtocol,
)
from alos.domain.models.audit import AuditEvent, DecisionRecord
from alos.integrations.mcp_gateway import MCPGateway
from alos.logs.decision_log import DecisionLogger
from alos.logs.system_audit import SystemAuditLogger
from alos.logs.telemetry import TelemetryTracer, global_tracer


class _Bridge:
    def __init__(self, g: ALOSStateGraph) -> None:
        self._g = g

    def log_audit_event(self, ev: AuditEvent) -> dict[str, Any]:
        """Forward AuditEvent to legacy AuditLoggerProtocol."""
        return self._g.audit_logger.log_event(ev.step, ev.status, ev.reason, ev.metadata)

    def log_decision_record(self, r: DecisionRecord) -> dict[str, Any]:
        """Forward DecisionRecord to legacy DecisionLoggerProtocol."""
        skip = {"timestamp", "decision_id", "action_type", "trace_id", "span_id"}
        d, act = self._g.decision_logger, SimpleNamespace(action_type=r.action_type)
        return d.log_decision(action=act, **r.model_dump(exclude=skip))


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
        approval_gate: HumanApprovalGatePort | None = None,
    ) -> None:
        self.approval_gate = approval_gate
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

    def run(self, user_query: str) -> dict[str, Any]:
        """Execute dual-loop reasoning via Ring 2 DualLoopOrchestrator (Strangler-Fig)."""
        with self.tracer.span("state_graph.run", tags={"query_length": len(user_query)}) as root:
            tr, b, ca = self.tracer, _Bridge(self), self.context_assembler
            c_uc, p_uc = _uc.AssembleContextUseCase(ca, ca, tr), _uc.PlanActionUseCase(tracer=tr)
            e_uc = _uc.EvaluateActionUseCase(decision_logger=b, tracer=tr)
            args = (c_uc, p_uc, e_uc, self.mcp_gateway, self.approval_gate, b, tr)
            res = _uc.DualLoopOrchestrator(*args, self.MAX_SELF_CORRECTION_ATTEMPTS).run(user_query)
            res["final_action"] = res["final_action"].model_dump(mode="json")
            res["evaluation"] = res["evaluation"].model_dump(mode="json")
            if res.get("result") is not None:
                res["execution_response"] = res["result"]
            self.tracer.inc_counter("alos_agent_runs_total", labels={"status": res["status"]})
            res["trace_id"] = root.trace_id
        if getattr(root, "duration_ms", None) is not None:
            self.tracer.observe_histogram(
                "alos_agent_run_duration_ms",
                float(root.duration_ms),
                labels={"status": res["status"]},
            )
        return res
