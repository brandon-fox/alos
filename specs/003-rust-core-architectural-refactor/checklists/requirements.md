# Requirement Verification Checklist: System-Wide Refactor & Rust Core Integration

- **Feature ID**: `002-rust-core-architectural-refactor`
- **Created**: 2026-08-02
- **Status**: In Progress

---

## Functional Requirement Checklist

- [ ] `FR-001`: Test coverage fortification achieves >= 95% branch coverage.
- [ ] `FR-002`: Telemetry tracer (`alos.logs.telemetry`) captures execution spans and durations.
- [ ] `FR-003`: AST baseline snapshot (`tests/quality/ast_metrics_baseline.json`) created.
- [ ] `FR-004`: `alos_core_rs` Rust crate scaffolds with `maturin` and `pyo3`.
- [ ] `FR-005`: `alos_core_rs::search` SIMD BM25 scoring and vector similarity implemented.
- [ ] `FR-006`: `alos_core_rs::graph` `petgraph` wikilink traversal implemented.
- [ ] `FR-007`: `alos_core_rs::safety` zero-allocation rule evaluator implemented.
- [ ] `FR-008`: `alos_core_rs::journal` atomic JSONL writer with CRC32 implemented.
- [ ] `FR-009`: `alos.native` bridge implemented with pure-Python fallback.
- [ ] `FR-010`: `EvaluatorNode` refactored to use native safety evaluator.
- [ ] `FR-011`: `ContextAssembler` and memory engines refactored for async & native acceleration.
- [ ] `FR-012`: `alos.db.session` refactored with async SQLAlchemy 2.0 context managers.
- [ ] `FR-013`: AST quality gate verifies MI >= 85.0 and CC <= 7.
- [ ] `FR-014`: Performance benchmark harness verifies speedup SLAs.
- [ ] `FR-015`: ADR 0012 created, accepted, and verified via `pyadr check-adr-repo`.
