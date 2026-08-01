# Implementation Plan: Audit Logger & Runtime Decision Log (ADR)

**Branch**: `05-audit-and-decision-log` | **Date**: 2026-08-01 | **Spec**: [spec.md](./spec.md)

## Constitution Check

- ✅ Article II §3 — Audit Logging: every state transition appended to system_audit.jsonl
- ✅ Article III §1 — Decision Provenance: every evaluate_action() emits a Decision Log ADR record

## Project Structure

```text
alos/
└── logs/
    ├── __init__.py           # exports SystemAuditLogger, DecisionLogger
    ├── system_audit.py       # SystemAuditLogger
    └── decision_log.py       # DecisionLogger (NEW)

logs/                         # Runtime output directory
├── system_audit.jsonl        # Append-only execution trail
└── decision_log.jsonl        # Append-only ADR decision records
```

## API Contracts

### SystemAuditLogger (existing)
```python
class SystemAuditLogger:
    def log_event(
        self, step: str, status: str, reason: Optional[str] = None, metadata: Optional[Dict] = None
    ) -> Dict: ...
```

### DecisionLogger (NEW)
```python
class DecisionLogger:
    def __init__(self, log_file_path: Optional[str] = None): ...
    def log_decision(
        self,
        trigger: str,
        action: BaseAction,
        risk_level: RiskLevel,
        decision: str,  # "APPROVED" | "REJECTED"
        rationale: str,
        constitution_articles_checked: List[str],
        preferences_checked: List[str],
        corrections_checked: List[str],
        alternatives_considered: List[str],
        self_correction_rounds: int,
    ) -> Dict: ...
```

### EvaluatorNode (modified)
```python
class EvaluatorNode:
    def __init__(
        self,
        context: Optional[ContextPayload] = None,
        decision_logger: Optional[DecisionLogger] = None,
        trigger: str = "",
    ): ...
```

### ALOSStateGraph (modified)
- Creates `DecisionLogger` instance shared across all evaluator calls
- Passes `trigger` (user_query) through to `EvaluatorNode`
- Accumulates `alternatives_considered` list between rejection rounds

## Decision Log Record Schema

```json
{
  "timestamp": "2026-08-01T14:00:00.000000",
  "decision_id": "D-001",
  "trigger": "Schedule meeting Team Sync for today",
  "action_type": "google_calendar_create_event",
  "risk_level": "MEDIUM",
  "decision": "APPROVED",
  "rationale": "Event at 14:00 satisfies 'No meetings after 5:00 PM'. Risk MEDIUM, no approval required.",
  "constitution_articles_checked": ["I §1", "V"],
  "preferences_checked": ["No meetings scheduled after 5:00 PM"],
  "corrections_checked": [],
  "alternatives_considered": ["google_calendar_create_event at T17:30 — REJECTED: Violates preference: No meetings scheduled after 5:00 PM"],
  "self_correction_rounds": 1
}
```
