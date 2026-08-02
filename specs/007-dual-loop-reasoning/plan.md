# Implementation Plan: Dual-Loop Reasoning & Evaluator Self-Correction

**Branch**: `02-dual-loop-reasoning` | **Date**: 2026-08-01 | **Spec**: [spec.md](./spec.md)

---

## Summary

The reasoning core implements a Planner → Evaluator → Planner loop. The Evaluator validates drafted actions against ContextPayload rules. On rejection, structured critique is fed back to the Planner. The State Graph caps the loop at 5 iterations.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: pydantic>=2.0
**Testing**: pytest, tmp_path fixtures
**Project Type**: Library module — no network calls in core reasoning loop

## Constitution Check

- ✅ Article I §1 — No external mutation before Plan/Draft → Validate gate
- ✅ Article I §2 — Pydantic schemas mandatory for all action payloads
- ✅ Article III §2 — Decision Provenance: every evaluate_action() call emits a Decision Log entry (enforced in Feature 05)
- ✅ Article IV — TDD: tests written before implementation

## API Contracts

### EvaluatorNode
```python
class EvaluatorNode:
    def __init__(self, context: Optional[ContextPayload] = None): ...
    def classify_risk(self, action: BaseAction) -> RiskLevel: ...
    def evaluate_action(self, action: BaseAction) -> EvaluationResult: ...
```

### PlannerNode
```python
class PlannerNode:
    def __init__(self, context: ContextPayload): ...
    def generate_draft_action(
        self, user_query: str, critique_feedback: Optional[str] = None
    ) -> BaseAction: ...
```

### ALOSStateGraph
```python
class ALOSStateGraph:
    def run(self, user_query: str) -> Dict[str, Any]:
        # Returns: {status, final_action, self_correction_attempts, execution_response}
```

## State Flow

```
[Trigger] → ContextAssembler → PlannerNode
                                    ↓
                              EvaluatorNode
                             /            \
                    REJECTED               APPROVED
                    (loop back)           (dispatch MCP)
                        ↑
              critique_feedback → PlannerNode (round N)
```
