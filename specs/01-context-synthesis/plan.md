# Implementation Plan: Context Synthesis & Local Vault RAG Retrieval

**Branch**: `01-context-synthesis` | **Date**: 2026-08-01 | **Spec**: [spec.md](./spec.md)

---

## Summary

The Context Assembler reads three canonical vault Markdown files plus performs keyword-ranked search over all vault notes to assemble a `ContextPayload` for the reasoning core. All processing is strictly local — no network calls.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: pydantic>=2.0, pathlib, glob
**Storage**: Local filesystem — `vault/*.md`
**Testing**: pytest, tmp_path fixtures
**Target Platform**: Local (Windows / Linux compatible)
**Project Type**: Library module
**Performance Goals**: < 500ms for 100-note vault
**Constraints**: No network access permitted; graceful degradation on missing files

## Constitution Check

- ✅ Article II §1 — All processing local only, no external calls
- ✅ Article IV — Tests written before implementation (RED → GREEN)
- ✅ FR-006 — Graceful degradation: empty ContextPayload on missing vault

## Project Structure

```text
alos/
├── memory/
│   ├── __init__.py
│   └── vector_store.py       # LocalVectorStore
├── core/
│   ├── __init__.py
│   └── context_assembler.py  # ContextAssembler + ContextPayload

vault/
├── USER_PROFILE.md
├── PREFERENCES.md
└── CORRECTION_LEDGER.md

tests/
├── features/
│   └── 01_context_synthesis.feature   # BDD Gherkin acceptance scenarios
└── test_sdd_bdd_features.py           # TDD test cases for this feature
```

## API Contracts

### ContextPayload (Pydantic Model)
```python
class ContextPayload(BaseModel):
    profile: Dict[str, Any]  # Parsed from USER_PROFILE.md
    preferences: List[str]  # Lines from PREFERENCES.md
    corrections: List[str]  # Lines from CORRECTION_LEDGER.md
    rag_docs: List[Dict[str, Any]]  # Top-k ranked vault documents
```

### ContextAssembler
```python
class ContextAssembler:
    def __init__(self, vault_dir: str): ...
    def assemble_context(self, user_query: str) -> ContextPayload: ...
```

### LocalVectorStore
```python
class LocalVectorStore:
    def __init__(self, vault_dir: str): ...
    def search(self, query: str, top_k: int = 5) -> List[Dict]: ...

    # Returns: [{"filename", "filepath", "content", "score"}]
```
