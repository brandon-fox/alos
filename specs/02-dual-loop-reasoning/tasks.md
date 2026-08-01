# Tasks: Dual-Loop Reasoning & Evaluator Self-Correction

**Input**: `specs/02-dual-loop-reasoning/spec.md`, `specs/02-dual-loop-reasoning/plan.md`

---

## Phase 1: Foundational — Schemas

- [x] T001 Define `RiskLevel` Enum (LOW, MEDIUM, HIGH) in `alos/core/evaluator.py`
- [x] T002 Define `EvaluationResult` Pydantic model in `alos/core/evaluator.py`

## Phase 2: User Story 1 — Evaluator Validation (P1)

### Tests (TDD — Write FIRST, confirm RED)

- [x] T003 [US1] `test_02_dual_loop_reasoning_evaluator_rejection` — **confirm RED**
- [x] T004 [US1] `test_02_dual_loop_reasoning_evaluator_approval` — **confirm RED**

### Implementation

- [x] T005 [US1] Implement `EvaluatorNode.classify_risk()` mapping action types to RiskLevel
- [x] T006 [US1] Implement `EvaluatorNode.evaluate_action()` with ISO-8601 time constraint checking against preferences
- [x] T007 [US1] Implement correction ledger checking in `evaluate_action()`
- [x] T008 [US1] Run pytest — **confirm GREEN**

## Phase 3: User Story 2 — Planner Self-Correction Loop (P1)

### Tests (TDD — Write FIRST, confirm RED)

- [x] T009 [US2] `test_06_end_to_end_state_graph_dual_loop` — assert `self_correction_attempts >= 1`, final time before 17:00 — **confirm RED**

### Implementation

- [x] T010 [US2] Implement `PlannerNode.generate_draft_action()` with `critique_feedback` parameter
- [x] T011 [US2] Implement `ALOSStateGraph.run()` dual-loop with 5-attempt cap
- [x] T012 [US2] Wire critique feedback from Evaluator back to Planner on rejection
- [x] T013 [US2] Return `status: FAILED` when max attempts exceeded
- [x] T014 [US2] Run pytest — **confirm GREEN**

## Phase 4: Polish

- [x] T015 [P] Move BDD Gherkin to `tests/features/02_dual_loop_reasoning.feature`
- [x] T016 [P] Verify checklist requirements met
