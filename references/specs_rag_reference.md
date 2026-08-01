# ALOS Consolidated RAG Reference & Knowledge Base

This reference document synthesizes key system architecture specifications, safety matrices, decision logging contracts, and vault schemas into a structured reference manual for local RAG retrieval.

---

## 1. System Architecture & Dual-Loop Reasoning

```
  [User Request / Goal]
            │
            ▼
┌──────────────────────┐
│  Context Synthesizer │ ◄── [Vault: User Profile, Preferences, Ledger]
└──────────┬───────────┘
           │ Synthesized Context
           ▼
┌──────────────────────┐
│    Outer Planner     │ ──► Proposes Candidate Action Plan (Pydantic)
└──────────┬───────────┘
           │ Candidate Plan
           ▼
┌──────────────────────┐
│   Inner Evaluator    │ ◄── [Constitution & Safety Matrix]
└──────────┬───────────┘
           ├── APPROVED ──► [Decision Log ADR] ──► [MCP Executor]
           └── REJECTED ──► [Self-Correction Critique] (Up to 3 rounds)
```

---

## 2. Safety Matrix & Approval Tiers

| Tier | Actions | Autonomy & Approval Gate |
|---|---|---|
| **LOW** | Read-only vault search, local specs lookup, log inspection | Fully autonomous. Zero human prompts. |
| **MEDIUM** | Draft creation (Todoist draft, calendar event draft, local note) | Autonomous with Pydantic schema validation. |
| **HIGH** | External email dispatch, calendar item deletion, financial API execution | REQUIRES explicit human approval before MCP tool call. |

---

## 3. Decision Log ADR Schema (`logs/decision_log.jsonl`)

```json
{
  "timestamp": "2026-08-01T14:00:00Z",
  "decision_id": "D-001",
  "trigger": "User request for calendar schedule",
  "action_type": "calendar.create_event",
  "risk_level": "MEDIUM",
  "decision": "APPROVED",
  "rationale": "Action is a draft event within user preferred working hours",
  "constitution_articles_checked": ["I §1", "V §1"],
  "preferences_checked": ["No meetings before 9 AM"],
  "corrections_checked": [],
  "alternatives_considered": ["Direct external invite - rejected due to HIGH risk tier"],
  "self_correction_rounds": 0
}
```

---

## 4. Vault Memory Structures (`vault/`)

- `USER_PROFILE.md`: Personal data, role, working hours, key contacts.
- `PREFERENCES.md`: Soft rules, calendar preferences, communication tone.
- `CORRECTION_LEDGER.md`: Immutable log of past user corrections to prevent repeating mistakes.

---

## 5. Specification Index

- **Feature 01**: Context Synthesis (`specs/01-context-synthesis/spec.md`)
- **Feature 02**: Dual-Loop Reasoning (`specs/02-dual-loop-reasoning/spec.md`)
- **Feature 03**: Safety Matrix (`specs/03-safety-matrix/spec.md`)
- **Feature 04**: MCP Integrations (`specs/04-mcp-integrations/spec.md`)
- **Feature 05**: Audit & Decision Log (`specs/05-audit-and-decision-log/spec.md`)
- **Feature 06**: RAG & Knowledge Base (`specs/06-rag-and-knowledge-base/spec.md`)
