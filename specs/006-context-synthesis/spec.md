# Feature Specification: Context Synthesis & Local Vault RAG Retrieval

**Feature Branch**: `01-context-synthesis`

**Created**: 2026-08-01

**Status**: Active

**Constitution Reference**: `.specify/memory/constitution.md` — Article II (Local-First Privacy), Article III (Decision Provenance)

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Vault Context Assembly (Priority: P1)

Alex submits a life logistics task. Before ALOS plans any action, it reads the local Markdown vault to understand Alex's preferences, profile, and past correction history so that no action violates a known rule.

**Why this priority**: Without context, every plan is uninformed and likely to violate preferences. This is the foundational read step.

**Independent Test**: Can be fully tested by calling `ContextAssembler.assemble_context()` with a populated `tmp_path` vault and asserting returned `ContextPayload` contains expected rules.

**Acceptance Scenarios**:

1. **Given** `PREFERENCES.md` contains "No meetings scheduled after 5:00 PM", **When** `assemble_context("Plan my schedule")` is called, **Then** the returned `ContextPayload.preferences` list includes that exact string.
2. **Given** `CORRECTION_LEDGER.md` contains "Never book flights without checking Delta options first", **When** context is assembled, **Then** `ContextPayload.corrections` includes that entry.
3. **Given** `USER_PROFILE.md` contains `User: Alex`, **When** context is assembled, **Then** `ContextPayload.profile["User"] == "Alex"`.

---

### User Story 2 — Semantic Search over Vault Notes (Priority: P2)

Alex has unstructured notes in the vault. When a task is submitted, ALOS performs a keyword-ranked search over all Markdown files to surface the most relevant context documents.

**Why this priority**: Structured profile files (US1) cover known fields; semantic search surfaces ad-hoc notes.

**Independent Test**: Call `LocalVectorStore.search(query)` against a vault with known content, assert ranked results contain the most relevant file.

**Acceptance Scenarios**:

1. **Given** a vault with a note containing "San Francisco travel plan", **When** `search("San Francisco trip")` is called, **Then** that note appears in the top results.
2. **Given** a query with zero matching terms, **When** `search()` is called, **Then** an empty list is returned without error.

---

### Edge Cases

- What happens when the vault directory does not exist? `ContextAssembler` must return an empty `ContextPayload` without raising an exception.
- What happens when a vault file is empty? The file is skipped silently; no entry is added to preferences or corrections.
- What happens when a preference line contains special characters? The line is included as-is without sanitization.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST read `USER_PROFILE.md`, `PREFERENCES.md`, and `CORRECTION_LEDGER.md` from the configured vault directory on every `assemble_context()` call.
- **FR-002**: System MUST parse `PREFERENCES.md` lines starting with `-` as individual preference strings.
- **FR-003**: System MUST parse `CORRECTION_LEDGER.md` lines starting with `-` as individual correction strings.
- **FR-004**: System MUST return a typed `ContextPayload` (Pydantic model) containing `profile`, `preferences`, `corrections`, and `rag_docs`.
- **FR-005**: `LocalVectorStore.search()` MUST rank Markdown files by keyword match score and return the top-k results.
- **FR-006**: System MUST NOT raise exceptions when vault files are missing or empty — graceful degradation required.

### Key Entities

- **ContextPayload**: `profile: Dict`, `preferences: List[str]`, `corrections: List[str]`, `rag_docs: List[Dict]`
- **LocalVectorStore**: `vault_dir: str`, `search(query: str, top_k: int) -> List[Dict]`

---

## Success Criteria *(mandatory)*

- **SC-001**: `ContextAssembler.assemble_context()` returns a valid `ContextPayload` within 500ms for a vault of up to 100 notes.
- **SC-002**: All preference and correction lines present in vault files appear in the returned `ContextPayload`.
- **SC-003**: `LocalVectorStore.search()` returns the correct top-ranked file for any single-keyword query against a 10-file test vault.
- **SC-004**: Zero exceptions raised when vault is missing, empty, or partially populated.

---

## Assumptions

- Vault notes are UTF-8 encoded plain Markdown files.
- `USER_PROFILE.md` key-value pairs use `Key: Value` format.
- Preference and correction lines are prefixed with `- `.
- Semantic ranking is keyword-frequency based in v1 (no embedding model required).
