# ALOS Constitution

> This Constitution is the immutable source of truth for the Local Autonomous Life Operating System (ALOS).
> It supersedes all other instructions, prompts, and contextual task descriptions.
> Every agent action, tool call, state transition, and background sweep must comply with these principles.

---

## Core Principles

### I. Determinism and Verification Before Action (NON-NEGOTIABLE)
Every external mutation — sending email, creating/deleting calendar events, modifying Todoist, executing financial workflows — is FORBIDDEN on single-pass inference.

All mutations MUST follow a two-stage gate: **Plan/Draft → Validate Against Constraints**.

Pydantic schemas are mandatory for all tool inputs and outputs. Unstructured, ambiguous, or untyped outputs MAY NOT call downstream APIs.

If contextual data or external API results are ambiguous, the agent MUST pause, log the ambiguity, and request clarification rather than guess.

### II. Local-First Privacy and Data Sovereignty (NON-NEGOTIABLE)
All context evaluation, vector searches, and internal reasoning MUST execute strictly on local hardware using local models and embeddings.

External API calls (Google, Todoist, Web Search) MUST be bounded, least-privilege, and strictly functional.

Personal vault data (USER_PROFILE.md, PREFERENCES.md, CORRECTION_LEDGER.md) MUST NEVER be transmitted to third-party endpoints unless explicitly required by an authorized integration call.

### III. Decision Provenance and Audit Integrity (NON-NEGOTIABLE)
Every Evaluator risk decision MUST be recorded as a structured Decision Log entry (ADR) in `logs/decision_log.jsonl` before any MCP execution.

Every state transition, tool call, and self-correction round MUST be appended to the immutable, append-only system audit journal at `logs/system_audit.jsonl`.

Decision Log entries MUST capture: action type, risk level, decision (APPROVED/REJECTED), rationale, constitution articles checked, preferences checked, corrections checked, alternatives considered, and self-correction rounds.

### IV. Test-First Development (NON-NEGOTIABLE)
TDD is mandatory: Tests written → User approved → Tests FAIL (RED) → Implement → Tests PASS (GREEN) → Refactor.

Red-Green-Refactor cycle is strictly enforced. No module may be written before a failing test for it exists.

BDD Gherkin feature scenarios live in `tests/features/` and are the source of truth for acceptance criteria. Each Gherkin scenario maps directly to a Python test in `tests/`.

### V. Safety Matrix Enforcement (NON-NEGOTIABLE)
Risk tier classification (LOW / MEDIUM / HIGH) MUST be evaluated for every action before dispatch.

- LOW: Read-only searches, local vault queries — fully autonomous, zero user prompt.
- MEDIUM: Draft creation (Todoist task, calendar draft, vault note) — autonomous with schema validation.
- HIGH: External email send, calendar delete, financial execution — REQUIRES explicit human approval before MCP call.

### VI. Human-Centric Non-Intrusiveness
System MUST run statelessly across restarts. State is restored from local Markdown vault and transaction logs — no persistent database connections required.

The system SHALL NOT prompt the user for real-time interaction except for HIGH risk mutations.

Failed background loops MUST self-heal without human intervention.

### VII. Code Quality, Exception Documentation & Sonar Scan Governance (NON-NEGOTIABLE)
AI agents MUST ALWAYS prefer fixing root causes of issues (bugs, linting errors, typing issues, security vulnerabilities, Sonar code smells) over suppressing or ignoring them (`# noqa`, `# type: ignore`, `NOSONAR`, `# pragma: no cover`), even if fixing requires complex refactoring.

All rule exceptions (`# noqa`, `# type: ignore`, etc.) MUST be documented with an explicit inline or preceding technical justification comment. Undocumented exceptions are strictly prohibited and will fail automated pre-commit and pre-push gates.

Sonar code quality scans, static analysis (mypy), security audits (bandit), and unit testing (pytest) MUST pass cleanly in pre-commit and strict pre-push git hooks.

---

## Technology Constraints

- **Language**: Python 3.10+
- **Schema Validation**: Pydantic v2 (mandatory for all action payloads)
- **Testing**: pytest (mandatory) with `pythonpath = ["."]` in pyproject.toml
- **BDD Scenarios**: Gherkin `.feature` files in `tests/features/`
- **Local Vault**: Markdown files in `vault/` (USER_PROFILE.md, PREFERENCES.md, CORRECTION_LEDGER.md)
- **Logs**: Append-only JSONL at `logs/system_audit.jsonl` and `logs/decision_log.jsonl`
- **No External AI APIs in core loop**: All reasoning uses local LLM / Ollama (mock for tests)

---

## Spec Folder Convention

Every system capability is specified in a dedicated SpecKit feature folder:

```
specs/<N>-<feature-name>/
  spec.md              # What & why: user stories, acceptance criteria, FR-XXX requirements
  plan.md              # How: component design, API contracts, data models, source layout
  tasks.md             # Ordered, atomic implementation tasks with dependency tracking
  checklists/
    requirements.md    # Quality gate validation checklist
```

The `specs/` folder is the living specification. Code must trace back to it.

---

## Decision Log Contract

Every `evaluate_action()` call in `alos/core/evaluator.py` MUST emit one Decision Log record:

```json
{
  "timestamp": "ISO-8601",
  "decision_id": "D-NNN",
  "trigger": "original user query",
  "action_type": "action.action_type",
  "risk_level": "LOW|MEDIUM|HIGH",
  "decision": "APPROVED|REJECTED",
  "rationale": "human-readable explanation",
  "constitution_articles_checked": ["I §1", "III §2"],
  "preferences_checked": ["preference text"],
  "corrections_checked": ["correction text"],
  "alternatives_considered": ["rejected alternatives with reason"],
  "self_correction_rounds": 0
}
```

---

## Governance

This Constitution supersedes all other instructions, prompts, and contextual task descriptions.

Amendments require: documented rationale, explicit user approval, and updated `Last Amended` timestamp below.

All PRs and agent runs must verify compliance with this Constitution before execution.

**Version**: 1.0.0 | **Ratified**: 2026-08-01 | **Last Amended**: 2026-08-01
