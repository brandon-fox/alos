# Feature Specification: Audit Logger & Runtime Decision Log (ADR)

**Feature Branch**: `05-audit-and-decision-log`

**Created**: 2026-08-01

**Status**: Active

**Constitution Reference**: `.specify/memory/constitution.md` — Article III §1 (Decision Provenance), Article II §3 (Audit Logging)

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — System Audit Logger (Priority: P1)

Every state transition, tool call, and self-correction loop emits an append-only JSONL record to `logs/system_audit.jsonl`. Alex must be able to inspect the full execution trail after any run.

**Acceptance Scenarios**:

1. **Given** an initialized `SystemAuditLogger` targeting a `tmp_path` log file, **When** `log_event(step="Context Assembly", status="SUCCESS")` and `log_event(step="Evaluator Check", status="REJECTED", reason="Preference Violation")` are called, **Then** the log file contains exactly 2 valid JSONL lines with correct `step`, `status`, `reason`, and `timestamp` fields.

---

### User Story 2 — Runtime Decision Log (ADR) (Priority: P1)

Every call to `EvaluatorNode.evaluate_action()` must emit a structured Decision Log ADR entry to `logs/decision_log.jsonl`. This record captures the full provenance: what action was considered, why it was approved or rejected, which constitution articles were checked, what alternatives were rejected, and how many self-correction rounds occurred.

**Why this priority**: Without decision provenance, ALOS is a black box. The ADR log is the audit trail for human review and system self-improvement.

**Independent Test**: Call `EvaluatorNode.evaluate_action()` (with a `DecisionLogger` injected) for a rejected action; inspect `logs/decision_log.jsonl` for a well-formed ADR record with all required fields populated.

**Acceptance Scenarios**:

1. **Given** `EvaluatorNode` with a `DecisionLogger`, **When** a `GoogleCalendarEvent` at 5:30 PM is evaluated, **Then** `decision_log.jsonl` contains one record with `decision: "REJECTED"`, `rationale` referencing the preference, and `constitution_articles_checked: ["I §1"]`.
2. **Given** a State Graph run that self-corrects once, **When** the final APPROVED decision is logged, **Then** the ADR entry includes `alternatives_considered` listing the rejected 5:30 PM slot with reason, and `self_correction_rounds: 1`.

---

### Edge Cases

- What if the log file directory does not exist? `SystemAuditLogger` and `DecisionLogger` MUST create parent directories automatically.
- What if a log write fails (e.g., disk full)? Log the error to stderr; do not crash the execution pipeline.
- What if `alternatives_considered` is empty on first pass? The field is an empty list `[]`; it is only populated after at least one rejection.

---

## Requirements *(mandatory)*

### Functional Requirements

#### SystemAuditLogger
- **FR-001**: `log_event(step, status, reason, metadata)` MUST append one JSONL record per call.
- **FR-002**: Every JSONL record MUST contain: `timestamp` (ISO-8601), `step`, `status`, `reason`, `metadata`.
- **FR-003**: Log file MUST be created (including parent directories) if it does not exist.
- **FR-004**: Log file MUST be strictly append-only — existing records MUST NOT be modified.

#### DecisionLogger
- **FR-005**: `log_decision(...)` MUST append one JSONL record per call to `logs/decision_log.jsonl`.
- **FR-006**: Every Decision Log record MUST contain:
  - `timestamp` (ISO-8601)
  - `decision_id` (auto-incrementing string, e.g. "D-001")
  - `trigger` (original user query string)
  - `action_type` (action.action_type)
  - `risk_level` (LOW | MEDIUM | HIGH)
  - `decision` (APPROVED | REJECTED)
  - `rationale` (human-readable explanation of the decision)
  - `constitution_articles_checked` (list of article references checked, e.g. ["I §1", "V"])
  - `preferences_checked` (list of preference strings evaluated)
  - `corrections_checked` (list of correction strings evaluated)
  - `alternatives_considered` (list of rejected alternative descriptions with reasons)
  - `self_correction_rounds` (integer count of prior rejection rounds)
- **FR-007**: `DecisionLogger` MUST be injectable into `EvaluatorNode` as a constructor dependency.
- **FR-008**: `ALOSStateGraph` MUST accumulate `alternatives_considered` across rejection rounds and pass to final APPROVED decision record.

### Key Entities

- **SystemAuditLogger**: `log_file_path: str`, `log_event(...) -> Dict`
- **DecisionLogger**: `log_file_path: str`, `log_decision(trigger, action, risk_level, decision, rationale, ...) -> Dict`

---

## Success Criteria *(mandatory)*

- **SC-001**: Every `evaluate_action()` call produces exactly one Decision Log record.
- **SC-002**: `alternatives_considered` is populated with at least one entry when `self_correction_rounds >= 1`.
- **SC-003**: All Decision Log records are valid, parseable JSONL with all 12 required fields present.
- **SC-004**: Audit and Decision log files persist correctly across simulated process restarts (i.e., append-only behavior verified).

---

## Assumptions

- `decision_id` is auto-incremented per session (session-scoped counter, not globally unique across restarts in v1).
- The `trigger` field captures the original user query passed to `ALOSStateGraph.run()`.
- `constitution_articles_checked` is statically defined per rule check type (not dynamically discovered).
