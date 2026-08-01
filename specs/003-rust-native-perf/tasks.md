# Tasks: Rust Native Performance Extensions (PyO3 + Maturin)

**Branch**: `feat/003-rust-native-perf` | **Spec**: [specs/003-rust-native-perf/spec.md](file:///c:/Users/bfoxt/n8nSetup/specs/003-rust-native-perf/spec.md)

## Tasks

- [x] **Task 1: ADR & Decision Provenance Recording** (FR-001)
  - Execute `pyadr new "Use PyO3 and Maturin for Rust native performance extension"` using `pyadr` CLI.
  - Verify ADR rendered in `docs/adr/`.

- [x] **Task 2: Rust Crate Initialization & PyO3 Stub Setup** (FR-001, FR-006)
  - Create `crates/alos_native/Cargo.toml` with PyO3, Rayon, Serde, Regex, Petgraph dependencies.
  - Create stub PyO3 bindings in `crates/alos_native/src/lib.rs`.
  - Update `pyproject.toml` dependencies and build system configuration for maturin / setuptools-rust.

- [x] **Task 3: Unit & Parity Test Suite Creation (TDD - RED Phase)** (FR-002, SC-003)
  - Create `tests/test_rust_native_parity.py` with test cases asserting identical outputs between native bindings and pure-Python fallbacks.
  - Verify test suite runs cleanly with fallback mechanisms.

- [x] **Task 4: Fast Obsidian Vault Parser in Rust** (FR-003, SC-001)
  - Implement `vault.rs` using `rayon` for parallel scanning and regex for wikilink/tag extraction.
  - Expose `FastVaultParser` to Python via PyO3.
  - Update `alos.memory.obsidian_vault` to import and wrap `FastVaultParser` with fallback.

- [x] **Task 5: Fast Okapi BM25 Indexer in Rust** (FR-004, SC-002)
  - Implement `bm25.rs` for parallel term frequency and Okapi BM25 scoring.
  - Expose `FastBM25Indexer` to Python via PyO3.
  - Update `alos.memory.spec_rag` and `alos.memory.vector_store` to use `FastBM25Indexer` with fallback.

- [x] **Task 6: Fast Note Graph Traversal in Rust** (FR-005)
  - Implement `graph.rs` using `petgraph` for BFS graph neighborhood reachability.
  - Expose `FastGraphEngine` to Python via PyO3.
  - Update `alos.memory.obsidian_graph` to use `FastGraphEngine` with fallback.

- [x] **Task 7: Verification, Benchmarking & Code Quality Audit** (SC-001, SC-002, SC-003, SC-004)
  - Run `pytest` test suites.
  - Run `ruff check`, `mypy`, `bandit`, and pre-commit hooks.
  - Verify clean execution of python fallback and native speedups.
