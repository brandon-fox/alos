# Feature Specification: LangGraph Autonomous Self-Reflection Loop for n8n Workflows

**Feature Branch**: `09-langgraph-n8n-self-reflection`

**Created**: 2026-08-01

**Status**: Active

**Constitution Reference**: `.specify/memory/constitution.md` — Article I (Determinism & Verification), Article III (Decision Provenance)

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — LangGraph Evaluates n8n Polling Output and Triggers Self-Correction (Priority: P1)

When an n8n workflow returns an incomplete payload or error status during autonomous execution or polling, the LangGraph Evaluator Node detects the failure, constructs structured critique feedback, and routes back to the Refinement Node to self-correct the payload parameters before retrying.

**Why this priority**: Repetitive or polling n8n tasks frequently encounter transient payload errors or missing parameters; self-correction ensures autonomous resiliency.

**Independent Test**: Instantiate `N8nSelfReflectionGraph`, pass an initial failing task payload, assert that `attempt_count` increments, critique is recorded, and subsequent corrected payload results in `status == "success"`.

**Acceptance Scenarios**:

1. **Given** an n8n polling task with missing required parameters, **When** `N8nSelfReflectionGraph.run()` is invoked, **Then** `evaluate_response` returns `valid == False`, `refine_payload` updates the parameters, and the next attempt succeeds.
2. **Given** an n8n task that repeatedly fails, **When** `attempt_count` reaches `max_attempts` (default 3), **Then** the graph transitions to `finalize_execution` with `status == "failed_max_retries"`.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `N8nTaskState` MUST maintain `task_id`, `workflow_id`, `payload`, `execution_output`, `evaluation_result`, `attempt_count`, `max_attempts`, `status`, and `audit_log`.
- **FR-002**: `poll_or_execute_n8n_task` node MUST interface with `N8nClient` to execute or poll n8n workflows (or mock responses in mock mode).
- **FR-003**: `evaluate_n8n_response` node MUST validate response outputs against schema/quality requirements and return `EvaluationResult(valid=bool, critique=str)`.
- **FR-004**: `refine_task_parameters` node MUST update the task payload using critique feedback for retry attempts.
- **FR-005**: The graph MUST enforce a configurable cap on attempts (`max_attempts`).

---

## Success Criteria *(mandatory)*

- **SC-001**: 100% of failed initial executions with correctable critiques recover on attempt 2.
- **SC-002**: Graph terminates cleanly at `max_attempts` without infinite loops.
- **SC-003**: All state transitions and self-reflections are recorded to system audit logs.
