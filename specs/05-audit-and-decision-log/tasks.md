# Tasks: Audit Logger & Runtime Decision Log (ADR)

**Input**: `specs/05-audit-and-decision-log/spec.md`, `specs/05-audit-and-decision-log/plan.md`

## Phase 1: User Story 1 — SystemAuditLogger (P1) [Already implemented; validate]

### Tests (TDD — confirm RED on first write, GREEN after impl)

- [x] T001 [US1] `test_05_audit_logging_append_only` — assert 2 JSONL records, all required fields present — **GREEN (existing)**

## Phase 2: User Story 2 — DecisionLogger ADR (P1) [NEW]

### Tests (TDD — Write FIRST, confirm RED)

- [x] T002 [US2] Write `test_07_decision_log_entry_structure` — assert all 12 required fields in one decision record — **RED → GREEN**
- [x] T003 [US2] Write `test_08_decision_log_alternatives_on_rejection` — assert `alternatives_considered` non-empty after one self-correction round — **RED → GREEN**

### Implementation

- [x] T004 [US2] Create `alos/logs/decision_log.py` with `DecisionLogger` class
- [x] T005 [US2] Implement auto-incrementing `decision_id` (session-scoped counter)
- [x] T006 [US2] Implement `log_decision()` method writing all 12 required fields to JSONL
- [x] T007 [US2] Update `alos/logs/__init__.py` to export `DecisionLogger`
- [x] T008 [US2] Inject `DecisionLogger` into `EvaluatorNode.__init__` as optional dep
- [x] T009 [US2] Call `decision_logger.log_decision(...)` at end of every `evaluate_action()`
- [x] T010 [US2] Update `ALOSStateGraph` to instantiate `DecisionLogger`, pass `trigger`, accumulate `alternatives_considered`
- [x] T011 [US2] Run pytest — **GREEN (9/9)**

## Phase 3: Polish

- [ ] T012 [P] Move Gherkin to `tests/features/05_audit_logging.feature`
- [ ] T013 [P] Verify checklist requirements met
