# Requirements Checklist: Safety Matrix & Risk Tier Enforcement

**Feature**: [spec.md](../spec.md)
**Created**: 2026-08-01

## Functional Requirements Gate

- [x] CHK001 FR-001: WebSearchQuery → RiskLevel.LOW
- [x] CHK002 FR-002: TodoistTaskCreate, GoogleCalendarEvent, VaultNoteUpdate → RiskLevel.MEDIUM
- [x] CHK003 FR-003: EmailDraft, email_send, calendar_delete, financial_transaction → RiskLevel.HIGH
- [x] CHK004 FR-004: Unknown action types → RiskLevel.HIGH (fail-safe)
- [x] CHK005 FR-005: evaluate_action() sets requires_approval=True for all HIGH risk results

## Constitution Compliance Gate

- [x] CHK006 Article V — All three safety tiers enforced
- [x] CHK007 Article I §1 — No HIGH mutation dispatched without requires_approval gate
