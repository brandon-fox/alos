# Tasks: Context Synthesis & Local Vault RAG Retrieval

**Input**: `specs/01-context-synthesis/spec.md`, `specs/01-context-synthesis/plan.md`

---

## Phase 1: Setup

- [x] T001 Create `alos/memory/` package with `__init__.py`
- [x] T002 Create `alos/core/` package with `__init__.py`
- [x] T003 Add `vault/` directory with default `USER_PROFILE.md`, `PREFERENCES.md`, `CORRECTION_LEDGER.md`

## Phase 2: Foundational — ContextPayload Schema

- [x] T004 Define `ContextPayload` Pydantic model in `alos/core/context_assembler.py`

## Phase 3: User Story 1 — Vault Context Assembly (P1)

### Tests (TDD — Write FIRST, confirm RED before implementation)

- [x] T005 [US1] Write `test_01_context_synthesis_from_vault` — assert preferences, corrections, profile loaded correctly — **confirm RED**

### Implementation

- [x] T006 [US1] Implement `ContextAssembler.__init__` and `assemble_context()` in `alos/core/context_assembler.py`
- [x] T007 [US1] Parse `USER_PROFILE.md` key-value pairs into `ContextPayload.profile`
- [x] T008 [US1] Parse `PREFERENCES.md` `-` lines into `ContextPayload.preferences`
- [x] T009 [US1] Parse `CORRECTION_LEDGER.md` `-` lines into `ContextPayload.corrections`
- [x] T010 [US1] Graceful degradation: return empty `ContextPayload` when files missing
- [x] T011 [US1] Run pytest — **confirm GREEN**

## Phase 4: User Story 2 — Semantic Search (P2)

### Tests (TDD — Write FIRST)

- [x] T012 [US2] Write `test_01b_vector_store_search_ranking` — assert top result matches keyword — **confirm RED**

### Implementation

- [x] T013 [US2] Implement `LocalVectorStore.search()` with keyword-frequency ranking in `alos/memory/vector_store.py`
- [x] T014 [US2] Integrate `LocalVectorStore` into `ContextAssembler.assemble_context()` as `rag_docs`
- [x] T015 [US2] Run pytest — **confirm GREEN**

## Phase 5: Polish

- [x] T016 [P] Move BDD Gherkin feature file to `tests/features/01_context_synthesis.feature`
- [x] T017 [P] Verify checklist requirements met
