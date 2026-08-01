# Spec 06 — RAG & Knowledge Base Engine

## User Story
As an ALOS autonomous agent, I need a fast, local-first retrieval engine to query system specifications (`specs/`), architectural references (`references/`), constitution constraints (`.specify/memory/constitution.md`), and user vault notes (`vault/`), so that I can ground every plan and evaluation in authoritative system knowledge.

## Acceptance Criteria
1. **Spec & Vault Coverage**: The RAG indexer MUST parse `.md` and `.feature` files across `specs/`, `vault/`, `references/`, and `.specify/memory/`.
2. **Section Header Indexing**: The RAG engine MUST break documents into searchable sections delineated by `#`, `##`, or `###` markdown headers.
3. **Keyword & Relevance Scoring**: The engine MUST calculate relevance scores based on query terms matching content and headers.
4. **Zero Cloud Dependency**: RAG indexing and search MUST run 100% locally without external API calls.

## Requirements
- **FR-06-01**: `SpecRAGIndexer` initializes with repository root path.
- **FR-06-02**: `SpecRAGIndexer.build_index()` loads all markdown specs, features, and vault notes.
- **FR-06-03**: `SpecRAGIndexer.search(query, top_k)` returns ranked dictionary containing header, section content, file path, and score.
