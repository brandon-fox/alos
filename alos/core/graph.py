"""ALOS State Graph — Dual-Loop Reasoning Orchestrator.

Spec: specs/02-dual-loop-reasoning/plan.md
Constitution: Article I §1, Article II §3, Article III §1
"""

from typing import Any, Dict, List, Optional

from alos.core.context_assembler import ContextAssembler
from alos.core.evaluator import EvaluatorNode
from alos.core.planner import PlannerNode
from alos.integrations.mcp_gateway import MCPGateway
from alos.logs.decision_log import DecisionLogger
from alos.logs.system_audit import SystemAuditLogger


class ALOSStateGraph:
    """State graph engine connecting all five ALOS layers.

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
        vault_dir: str,
        audit_log_path: Optional[str] = None,
        decision_log_path: Optional[str] = None,
    ):
        self.vault_dir = vault_dir
        self.context_assembler = ContextAssembler(vault_dir=vault_dir)
        self.mcp_gateway = MCPGateway(mock_mode=True)
        self.audit_logger = SystemAuditLogger(log_file_path=audit_log_path)
        self.decision_logger = DecisionLogger(log_file_path=decision_log_path)

    def run(self, user_query: str) -> Dict[str, Any]:
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

        critique_feedback: Optional[str] = None
        self_correction_rounds: int = 0
        alternatives_considered: List[str] = []
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
