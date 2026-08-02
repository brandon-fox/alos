# Tasks: Safety Matrix & Risk Tier Enforcement

**Input**: `specs/008-safety-matrix/spec.md`, `specs/008-safety-matrix/plan.md`

## Phase 1: User Story 1 — Risk Classification (P1)

### Tests (TDD — Write FIRST, confirm RED)

- [x] T001 [US1] `test_03_safety_matrix_risk_classification` — assert LOW/MEDIUM/HIGH for each action type — **confirm RED → GREEN**

### Implementation

- [x] T002 [US1] Implement `classify_risk()` with `isinstance` checks and `action_type` string fallback
- [x] T003 [US1] Add HIGH fail-safe for unknown action types

## Phase 2: User Story 2 — Approval Flag (P1)

- [x] T004 [US2] Set `requires_approval = (risk_level == RiskLevel.HIGH)` in `evaluate_action()`
- [x] T005 [US2] Verify `requires_approval: True` on EmailDraft evaluation result
- [x] T006 [US2] Run pytest — **confirm GREEN**

## Phase 3: Polish

- [x] T007 [P] Move Gherkin to `tests/features/03_safety_matrix.feature`
- [x] T008 [P] Verify checklist requirements met
