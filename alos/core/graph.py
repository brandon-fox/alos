"""ALOS State Graph — Dual-Loop Reasoning Orchestrator.

Spec: specs/02-dual-loop-reasoning/plan.md
Constitution: Article I §1, Article II §3, Article III §1
"""

from typing import Any

from alos.core.config import ALOSConfig
from alos.core.context_assembler import ContextAssembler
from alos.core.evaluator import EvaluatorNode
from alos.core.planner import PlannerNode
from alos.core.protocols import AuditLoggerProtocol, DecisionLoggerProtocol, MCPGatewayProtocol
from alos.integrations.mcp_gateway import MCPGateway
from alos.logs.decision_log import DecisionLogger
from alos.logs.system_audit import SystemAuditLogger


class ALOSStateGraph:
    """State graph engine connecting all five ALOS layers.

    Applies SOLID Dependency Inversion Principle (DIP) and 12-Factor Configuration (Factor III).
    Execution flow:
        ContextAssembler
            → PlannerNode (generates draft action)
            → EvaluatorNode (validates; emits Decision Log ADR)
                ↺ REJECTED: critique fed back to PlannerNode; alternative recorded
                ✓ APPROVED: dispatch via MCPGateway; log execution
            → SystemAuditLogger (appends state transitions)
            → DecisionLogger (appends ADR entries per evaluation)
    """

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
    ):
        self.config = config or ALOSConfig()

        resolved_vault_dir = vault_dir or self.config.vault_dir
        resolved_audit_path = audit_log_path or self.config.audit_log_path
        resolved_decision_path = decision_log_path or self.config.decision_log_path

        self.vault_dir = resolved_vault_dir
        self.context_assembler = ContextAssembler(vault_dir=resolved_vault_dir)

        # Injected abstractions or default factory instances (SOLID: DIP)
        self.mcp_gateway: MCPGatewayProtocol = (
            mcp_gateway if mcp_gateway is not None else MCPGateway(mock_mode=self.config.mock_mode)
        )
        self.audit_logger: AuditLoggerProtocol = (
            audit_logger
            if audit_logger is not None
            else SystemAuditLogger(log_file_path=resolved_audit_path)
        )
        self.decision_logger: DecisionLoggerProtocol = (
            decision_logger
            if decision_logger is not None
            else DecisionLogger(log_file_path=resolved_decision_path)
        )

    def run(self, user_query: str) -> dict[str, Any]:
        """Execute dual-loop reasoning state graph for the given user query."""
        # --- Layer 2: Context Synthesis ---
        context = self.context_assembler.assemble_context(user_query)
        self.audit_logger.log_event(
            step="Context Assembly",
            status="SUCCESS",
            metadata={
                "preferences_count": len(context.preferences),
                "corrections_count": len(context.corrections),
            },
        )

        planner = PlannerNode(context=context)
        evaluator = EvaluatorNode(
            context=context,
            decision_logger=self.decision_logger,
            trigger=user_query,
        )

        critique_feedback: str | None = None
        self_correction_rounds: int = 0
        alternatives_considered: list[str] = []
        final_action = None

        # --- Layer 3: Dual-Loop Reasoning ---
        while self_correction_rounds < self.MAX_SELF_CORRECTION_ATTEMPTS:
            draft_action = planner.generate_draft_action(
                user_query, critique_feedback=critique_feedback
            )

            eval_result = evaluator.evaluate_action(
                action=draft_action,
                alternatives_considered=list(alternatives_considered),
                self_correction_rounds=self_correction_rounds,
            )

            if eval_result.valid:
                self.audit_logger.log_event(
                    step="Evaluator Check",
                    status="APPROVED",
                    metadata={
                        "action": draft_action.action_type,
                        "risk_level": eval_result.risk_level.value,
                        "self_correction_rounds": self_correction_rounds,
                    },
                )
                final_action = draft_action
                break
            else:
                # Accumulate this rejected draft as an alternative_considered
                alternatives_considered.append(
                    f"{draft_action.action_type} at "
                    f"{getattr(draft_action, 'start_time', 'N/A')} — "
                    f"REJECTED: {eval_result.critique}"
                )
                self_correction_rounds += 1
                critique_feedback = eval_result.critique
                self.audit_logger.log_event(
                    step="Evaluator Check",
                    status="REJECTED",
                    reason=critique_feedback,
                    metadata={
                        "attempt": self_correction_rounds,
                        "action": draft_action.action_type,
                    },
                )

        if not final_action:
            self.audit_logger.log_event(
                step="State Graph",
                status="FAILED",
                reason="Max self-correction attempts exceeded",
                metadata={"max_attempts": self.MAX_SELF_CORRECTION_ATTEMPTS},
            )
            return {
                "status": "FAILED",
                "reason": "Max self-correction attempts reached without valid plan",
                "self_correction_attempts": self_correction_rounds,
            }

        # --- Layer 4: MCP Execution ---
        execution_response = self.mcp_gateway.execute_tool(
            final_action.action_type,
            final_action.model_dump(),
        )
        self.audit_logger.log_event(
            step="MCP Execution",
            status=execution_response.get("status", "SUCCESS"),
            metadata=execution_response,
        )

        return {
            "status": "SUCCESS",
            "final_action": final_action.model_dump(),
            "self_correction_attempts": self_correction_rounds,
            "execution_response": execution_response,
        }
