# Feature Specification: Rust Native Performance Extensions (PyO3 + Maturin)

**Feature Branch**: `feat/003-rust-native-perf`

**Created**: 2026-08-01

**Status**: Draft

**Input**: User description: "Rust native performance extensions using PyO3 and Maturin for ALOS memory and graph bottlenecks"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fast Vault Note Parsing (Priority: P1)

As an ALOS user with large Obsidian note vaults, I want note parsing (YAML frontmatter, inline tags, wikilinks) to be executed via a high-performance native engine so that indexing completes in milliseconds.

**Why this priority**: Obsidian vault indexing runs continuously during context assembly and RAG search; vault parsing is the largest I/O and text processing bottleneck.

**Independent Test**: Can be tested by running `ObsidianVaultParser.parse_all()` against a benchmark vault directory and verifying identical node structure output between Python and Rust native parsers with a >10x speedup.

**Acceptance Scenarios**:

1. **Given** a directory containing `.md` vault files, **When** `ObsidianVaultParser.parse_all()` is executed, **Then** all frontmatter, inline `#tags`, and `[[WikiLinks]]` are extracted identically to pure Python behavior.
2. **Given** an environment without compiled Rust binaries, **When** ALOS starts up, **Then** it transparently falls back to the pure Python `ObsidianVaultParser` without errors.

---

### User Story 2 - High-Speed BM25 Spec RAG Indexing & Search (Priority: P2)

As an ALOS assistant, I want document BM25 tokenization and scoring to be executed in native Rust so that context retrieval and spec RAG queries return instantly.

**Why this priority**: RAG search is performed frequently per user prompt to assemble context from specifications, vault notes, and system references.

**Independent Test**: Can be tested by querying `SpecRAGIndexer.search()` and `LocalVectorStore.search()` and comparing top-K ranked documents against the Python BM25 implementation.

**Acceptance Scenarios**:

1. **Given** a collection of markdown chunks and a search query, **When** `SpecRAGIndexer.search(query)` is called, **Then** scores match pure Python BM25Okapi rankings and results return significantly faster.

---

### User Story 3 - Rapid Graph Neighborhood Traversal (Priority: P3)

As an ALOS graph engine, I want note relationship graph construction and BFS neighborhood queries to use `petgraph` so that graph calculations do not block the event loop.

**Why this priority**: Multi-hop graph traversals scale super-linearly with vault size; native graph traversal ensures scalability for large memory graphs.

**Independent Test**: Can be tested by creating note graph links and calling `ObsidianGraphEngine.get_neighborhood(center_note, depth)` and asserting exact node set matches.

**Acceptance Scenarios**:

1. **Given** a graph of wikilink relationships, **When** `get_neighborhood` is called with depth K, **Then** the exact same set of reachable nodes is returned in under 5ms.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a Rust native crate (`crates/alos_native`) compiled via PyO3 exposing `FastVaultParser`, `FastBM25Indexer`, and `FastGraphEngine`.
- **FR-002**: System MUST transparently fall back to pure-Python implementations in `alos.memory.obsidian_vault`, `alos.memory.spec_rag`, and `alos.memory.obsidian_graph` if the native module is unavailable.
- **FR-003**: `FastVaultParser` MUST extract YAML frontmatter, inline `#tags`, and `[[WikiLinks]]` with identical parsing logic to `frontmatter.loads()` and Python regexes.
- **FR-004**: `FastBM25Indexer` MUST calculate Okapi BM25 scores matching `rank_bm25.BM25Okapi`.
- **FR-005**: `FastGraphEngine` MUST construct note wikilink graphs and evaluate BFS neighborhood reachability matching `networkx.single_source_shortest_path_length`.
- **FR-006**: System MUST configure `pyproject.toml` build system to support `maturin` / `setuptools-rust` while maintaining existing `pip` and `uv` setup compatibility.

### Key Entities

- **ObsidianNote**: Document entity containing file path, title, frontmatter dict, body content, extracted tags list, and wikilinks list.
- **SpecChunk**: RAG document chunk entity containing header, source type, path, content, and BM25 score.
- **GraphNeighborhood**: Reachable graph neighborhood entity containing center note and node set.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Vault note parsing throughput increases by at least 10x compared to pure Python.
- **SC-002**: BM25 query response time for 1,000+ chunks decreases to <5ms.
- **SC-003**: 100% test coverage and parity between pure Python fallbacks and Rust native implementations across pytest test suites.
- **SC-004**: Zero breaking changes to `alos.memory` public Python class signatures or protocols (`MemoryStoreProtocol`).

## Assumptions

- Rust toolchain (`cargo`, `rustc`) is available in build environments, but non-rust environments will operate seamlessly via pure-Python fallbacks.
- Maturin is used as the primary PyO3 build backend bridge for Python wheels/extensions.
