# Feature Specification: Dual-Loop Reasoning & Evaluator Self-Correction

**Feature Branch**: `02-dual-loop-reasoning`

**Created**: 2026-08-01

**Status**: Active

**Constitution Reference**: `.specify/memory/constitution.md` — Article I (Determinism & Verification), Article III (Decision Provenance)

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Evaluator Rejects Invalid Plan (Priority: P1)

Alex's preferences prohibit meetings after 5 PM. When the Planner drafts a 5:30 PM calendar event, the Evaluator must detect the violation and return a structured critique before any MCP call is made.

**Why this priority**: Without rejection, unsafe actions reach external APIs unchecked.

**Independent Test**: Instantiate `EvaluatorNode` with a `ContextPayload` containing the preference, pass a `GoogleCalendarEvent` at 5:30 PM, assert `evaluation.valid is False` and critique contains preference text.

**Acceptance Scenarios**:

1. **Given** preference "No meetings scheduled after 5:00 PM", **When** Evaluator receives a `GoogleCalendarEvent` at `T17:30`, **Then** `evaluation.valid == False` and critique references the violated preference.
2. **Given** the same preference, **When** Evaluator receives a `GoogleCalendarEvent` at `T14:00`, **Then** `evaluation.valid == True` and critique == "VALID".

---

### User Story 2 — Planner Self-Corrects After Rejection (Priority: P1)

After the Evaluator rejects a draft, the State Graph must route back to the Planner with the critique as feedback. The Planner must generate a corrected draft that avoids the violation.

**Why this priority**: Without the loop-back, the system is stateless and repeats the same mistake.

**Independent Test**: Run `ALOSStateGraph.run("Schedule meeting Team Sync for today")` against a vault with the after-5PM preference. Assert `result["self_correction_attempts"] >= 1` and final event start time is before 17:00.

**Acceptance Scenarios**:

1. **Given** a preference "No meetings after 5:00 PM" and an initial plan at 5:30 PM, **When** the State Graph runs the dual-loop, **Then** the final approved action is at 2:00 PM and `self_correction_attempts == 1`.

---

### Edge Cases

- What if the Planner cannot find a valid plan after 5 attempts? The graph must return `status: FAILED` with the last critique reason.
- What if there are no preferences? The Evaluator must approve all LOW/MEDIUM actions by default.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `EvaluatorNode.evaluate_action()` MUST check every `GoogleCalendarEvent` against preferences containing time constraints.
- **FR-002**: `EvaluatorNode.evaluate_action()` MUST return `EvaluationResult` with `valid: bool`, `critique: str`, `risk_level: RiskLevel`, `requires_approval: bool`.
- **FR-003**: The State Graph MUST loop back to Planner with critique feedback when `evaluation.valid == False`.
- **FR-004**: The Planner MUST use `critique_feedback` to generate a corrected draft on the next loop iteration.
- **FR-005**: The State Graph MUST cap self-correction at 5 attempts before returning `FAILED`.

### Key Entities

- **EvaluationResult**: `valid: bool`, `critique: str`, `risk_level: RiskLevel`, `requires_approval: bool`
- **RiskLevel**: `LOW | MEDIUM | HIGH` (Enum)

---

## Success Criteria *(mandatory)*

- **SC-001**: Evaluator correctly rejects calendar events after 5 PM on 100% of test cases.
- **SC-002**: Planner self-corrects within 1 loop for the time-preference scenario.
- **SC-003**: State Graph `FAILED` result is returned when max attempts are exceeded.
- **SC-004**: All correction loop iterations are logged to `logs/system_audit.jsonl`.

---

## Assumptions

- Preferences are stored as plain text strings; time detection uses ISO-8601 time substring matching.
- The Planner is LLM-driven in production; in tests it uses deterministic keyword routing.
- The dual-loop cap of 5 attempts prevents infinite recursion.
