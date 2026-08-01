# Feature Specification: Safety Matrix & Risk Tier Enforcement

**Feature Branch**: `03-safety-matrix`

**Created**: 2026-08-01

**Status**: Active

**Constitution Reference**: `.specify/memory/constitution.md` — Article I §1 (Safety Gate), Article V (Safety Matrix)

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Risk Tier Classification (Priority: P1)

Alex expects that reading data is fully autonomous, creating tasks happens automatically, and sending emails requires explicit approval. The Safety Matrix must classify every action before execution.

**Why this priority**: Incorrect risk classification could allow a HIGH risk action to bypass the approval gate.

**Independent Test**: Call `EvaluatorNode.classify_risk()` on `WebSearchQuery`, `TodoistTaskCreate`, and `EmailDraft` instances; assert LOW, MEDIUM, HIGH respectively.

**Acceptance Scenarios**:

1. **Given** a `WebSearchQuery` action, **When** `classify_risk()` is called, **Then** it returns `RiskLevel.LOW`.
2. **Given** a `TodoistTaskCreate` action, **When** `classify_risk()` is called, **Then** it returns `RiskLevel.MEDIUM`.
3. **Given** an `EmailDraft` action, **When** `classify_risk()` is called, **Then** it returns `RiskLevel.HIGH`.

---

### User Story 2 — HIGH Risk Actions Require Approval Flag (Priority: P1)

HIGH risk actions must set `requires_approval: True` on the `EvaluationResult` so the State Graph can intercept before dispatching to MCP.

**Acceptance Scenarios**:

1. **Given** an `EmailDraft` action, **When** `evaluate_action()` is called, **Then** `evaluation.requires_approval == True`.
2. **Given** a `WebSearchQuery` action, **When** `evaluate_action()` is called, **Then** `evaluation.requires_approval == False`.

---

### Edge Cases

- What if a new action type is not in any classification list? Default to HIGH (fail-safe, not fail-open).
- What if a `GoogleCalendarEvent` also involves deletion? The action type string must indicate delete to be HIGH.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `classify_risk()` MUST return `RiskLevel.LOW` for read-only/search actions.
- **FR-002**: `classify_risk()` MUST return `RiskLevel.MEDIUM` for draft-creation actions (Todoist tasks, calendar events, vault notes).
- **FR-003**: `classify_risk()` MUST return `RiskLevel.HIGH` for external send, delete, and financial actions.
- **FR-004**: Unknown action types MUST default to `RiskLevel.HIGH` (fail-safe).
- **FR-005**: `evaluate_action()` MUST set `requires_approval: True` for all HIGH risk actions.

---

## Success Criteria *(mandatory)*

- **SC-001**: `classify_risk()` returns correct tier for all 5 defined action types in < 1ms.
- **SC-002**: `requires_approval` is `True` for every HIGH risk evaluation result, `False` for LOW/MEDIUM.
- **SC-003**: Zero false-LOW classifications for externally-mutating actions.

---

## Assumptions

- Action type classification is based on `action.action_type` string and `isinstance()` type checks.
- The approval gate UI/interrupt is out of scope for this feature; `requires_approval` flag is the contract boundary.
