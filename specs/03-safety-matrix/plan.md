# Implementation Plan: Safety Matrix & Risk Tier Enforcement

**Branch**: `03-safety-matrix` | **Date**: 2026-08-01 | **Spec**: [spec.md](./spec.md)

## Constitution Check

- ✅ Article I §1 — HIGH risk actions require explicit approval; LOW/MEDIUM fully autonomous
- ✅ Article V — Safety Matrix tiers enforced for every action dispatch

## Risk Classification Table

| Action Type | Class | Risk Level |
|---|---|---|
| `WebSearchQuery` | `web_search` | LOW |
| `VaultNoteUpdate` | `vault_update_note` | MEDIUM |
| `TodoistTaskCreate` | `todoist_create_task` | MEDIUM |
| `GoogleCalendarEvent` (create) | `google_calendar_create_event` | MEDIUM |
| `EmailDraft` | `email_create_draft` | HIGH |
| `email_send` | string | HIGH |
| `calendar_delete` | string | HIGH |
| `financial_transaction` | string | HIGH |
| Unknown | any other | HIGH (fail-safe) |

## API Contract

```python
class EvaluatorNode:
    def classify_risk(self, action: BaseAction) -> RiskLevel:
        # isinstance checks first, then action_type string fallback
        # Unknown types → HIGH (fail-safe)
```
