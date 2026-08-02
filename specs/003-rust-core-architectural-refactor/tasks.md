# Task List: System-Wide Refactor & Rust Core Engine Integration

- **Feature ID**: `002-rust-core-architectural-refactor`
- **Created**: 2026-08-02
- **Status**: In Progress

---

## Stage 1: Pre-Refactor Test Fortification & Observability Overlay
- [x] Task 1.1: Create telemetry module `alos/logs/telemetry.py` with structured execution tracing and span tracking (`FR-002`).
- [x] Task 1.2: Create test coverage fortification suite `tests/test_coverage_fortification.py` to boost test coverage to >= 95% (`FR-001`).
- [x] Task 1.3: Create BDD Gherkin observability feature `tests/features/observability_and_tracing.feature` and pytest bindings (`FR-001`).
- [x] Task 1.4: Create AST anti-regression quality suite `tests/quality/test_code_quality_ast.py` and snapshot `tests/quality/ast_metrics_baseline.json` (`FR-003`).
- [x] Task 1.5: Create performance benchmark harness `tests/benchmarks/test_performance_benchmarks.py` and `tests/benchmarks/benchmark_reporter.py` (`NFR-001`).

## Stage 2: High-Performance Rust Native Core (`crates/alos_core_rs`)
- [x] Task 2.1: Scaffold Rust workspace `Cargo.toml` and crate `crates/alos_core_rs/Cargo.toml` with `maturin` and `pyo3` (`FR-004`).
- [x] Task 2.2: Implement `crates/alos_core_rs/src/lib.rs` and `src/search.rs` (SIMD BM25 & vector math) (`FR-005`).
- [x] Task 2.3: Implement `crates/alos_core_rs/src/graph.rs` (`petgraph` wikilink traversal) (`FR-006`).
- [x] Task 2.4: Implement `crates/alos_core_rs/src/safety.rs` (zero-allocation rule evaluator) (`FR-007`).
- [x] Task 2.5: Implement `crates/alos_core_rs/src/journal.rs` (atomic JSONL writer with CRC32) (`FR-008`).
- [x] Task 2.6: Create Python native bridge `alos/native/` with `bridge.py` and pure-Python fallback `fallback.py` (`FR-009`).

## Stage 3: Core Architecture Refactoring
- [x] Task 3.1: Refactor `alos/core/evaluator.py` to integrate `alos.native` safety evaluator (`FR-010`).
- [x] Task 3.2: Refactor `alos/memory/obsidian_graph.py` and `alos/memory/spec_rag.py` to integrate native graph & search acceleration (`FR-011`).
- [x] Task 3.3: Refactor `alos/logs/decision_log.py` to integrate native atomic journal writer (`FR-008`).
- [x] Task 3.4: Refactor `alos/db/session.py` to support SQLAlchemy 2.0 async session context managers (`FR-012`).

## Stage 4: Quality & Benchmark Verification, Docs & ADR Governance
- [x] Task 4.1: Verify AST anti-regression suite (`tests/quality/test_code_quality_ast.py`) passes with MI >= 85 and CC <= 7 (`FR-013`).
- [x] Task 4.2: Execute performance benchmark harness (`tests/benchmarks/test_performance_benchmarks.py`) and verify latency SLAs (`FR-014`).
- [x] Task 4.3: Propose and accept ADR `0012` via `pyadr`, regenerate TOC via `pyadr toc`, and run `pyadr check-adr-repo` (`FR-015`).
- [x] Task 4.4: Update `docs/architecture.md`, `docs/rust_engine_guide.md`, and `references/rust_core_reference.md`.
