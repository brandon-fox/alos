"""Dual-loop self-correcting orchestrator with explicit HIGH-risk approval gate (FR-3609)."""

from contextlib import nullcontext
from dataclasses import dataclass
from typing import Any

from alos.application import ports as _p
from alos.domain.models import BaseAction, ContextPayload
from alos.domain.models.audit import AuditEvent
from alos.domain.models.evaluation import EvaluationResult


@dataclass
class DualLoopOrchestrator:
    """Orchestrate Context -> Plan <-> Evaluate self-correction -> Approval Gate -> Execute."""

    context_uc: _p.AssembleContextHandler
    plan_uc: _p.PlanActionHandler
    eval_uc: _p.EvaluateActionHandler
    mcp_gateway: _p.MCPGatewayPort
    approval_gate: _p.HumanApprovalGatePort | None = None
    audit_logger: _p.AuditLoggerPort | None = None
    tracer: _p.TelemetryPort | None = None
    max_attempts: int = 5

    def _span(self, name: str, tags: dict[str, Any] | None = None) -> Any:
        return self.tracer.span(name, tags=tags) if self.tracer else nullcontext()

    def _aud(self, step: str, st: str, rsn: str | None = None, meta: Any = None) -> None:
        if self.audit_logger is not None:
            ev = AuditEvent(step=step, status=st, reason=rsn, metadata=meta or {})
            self.audit_logger.log_audit_event(ev)

    def _plan_eval(self, q: str, ctx: ContextPayload) -> tuple[BaseAction, EvaluationResult, int]:
        al: list[str] = []
        c: str | None = None
        rnd = 0
        while True:
            with self._span("planner.draft", {"attempt": rnd + 1}):
                draft = self.plan_uc.execute(q, ctx, c)
            with self._span("evaluator.evaluate", {"action": draft.action_type}):
                ev = self.eval_uc.execute(
                    draft, ctx, trigger=q, alternatives_considered=al, self_correction_rounds=rnd
                )
            st, rsn = ("APPROVED", None) if ev.valid else ("REJECTED", ev.critique)
            self._aud("Evaluator Check", st, rsn, {"attempt": rnd + 1})
            if ev.valid or (rnd := rnd + 1) >= self.max_attempts:
                return draft, ev, rnd
            al.append(f"{draft.action_type}: {ev.critique}")
            c = ev.critique

    def run(self, user_query: str) -> dict[str, Any]:
        """Run dual-loop planning, evaluation, approval gating, and MCP tool execution."""
        with self._span("context.assemble"):
            ctx = self.context_uc.execute(user_query)
            self._aud("Context Assembly", "SUCCESS", meta={"rag_docs": len(ctx.rag_docs)})
        act, ev, rnds = self._plan_eval(user_query, ctx)
        out: dict[str, Any] = {"status": "FAILED", "final_action": act, "evaluation": ev}
        out["result"], out["self_correction_attempts"] = None, rnds
        if not ev.valid:
            self._aud("State Graph", "FAILED", "Max self-correction attempts exceeded")
            return out
        if ev.requires_approval:
            g = self.approval_gate
            if not (g and g.request_approval(act, ev, trigger=user_query)):
                self._aud("Approval Gate", "PENDING_APPROVAL", "Human approval required")
                return {**out, "status": "PENDING_APPROVAL"}
            self._aud("Approval Gate", "APPROVED", meta={"action": act.action_type})
        with self._span("mcp.execute", {"action": act.action_type}):
            resp = self.mcp_gateway.execute_tool(act.action_type, act.model_dump())
            self._aud("MCP Execution", str(resp.get("status", "SUCCESS")), meta=resp)
        return {**out, "status": "SUCCESS", "result": resp}
