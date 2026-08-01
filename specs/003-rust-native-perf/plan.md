# Implementation Plan: Rust Native Performance Extensions (PyO3 + Maturin)

**Branch**: `feat/003-rust-native-perf` | **Date**: 2026-08-01 | **Spec**: [specs/003-rust-native-perf/spec.md](file:///c:/Users/bfoxt/n8nSetup/specs/003-rust-native-perf/spec.md)

**Input**: Feature specification from `specs/003-rust-native-perf/spec.md`

## Summary

This feature introduces a high-performance Rust native extension (`crates/alos_native`) compiled via **PyO3** and **Maturin** to eliminate performance bottlenecks in ALOS memory scanning, Okapi BM25 scoring, and NetworkX note graph traversals, while preserving 100% Python API compatibility and transparent pure-Python fallbacks.

## Technical Context

**Language/Version**: Python 3.10+, Rust 1.75+ (edition 2021), PyO3 0.20+
**Primary Dependencies**: `pyo3`, `rayon`, `serde`, `serde_yaml`, `regex`, `petgraph`, `maturin`
**Storage**: Local files / Obsidian Markdown notes / Spec Markdown documents
**Testing**: `pytest`, `cargo test`
**Target Platform**: Windows x86_64, Linux x86_64, macOS
**Project Type**: Python CLI & Library with Rust C-extension shared library (`.pyd` / `.so`)
**Performance Goals**: >10x speedup in vault parsing, <5ms BM25 queries across 1,000+ chunks, <2ms BFS graph traversals
**Constraints**: Zero breaking changes to `alos.memory` public APIs; graceful pure-Python fallback if Rust binary is missing.

## Constitution Check

- **Local-first Architecture**: Passed (All computations remain 100% local in memory/native CPU).
- **Test-Driven Development (TDD)**: Passed (Failing parity tests written before integration).
- **Decision Provenance & ADR**: Passed (`pyadr new` executed to document PyO3 architecture choice).
- **Fix-First Directive**: Passed (No `# noqa` or `# type: ignore` without explicit justification comments).

## Project Structure

```text
c:\Users\bfoxt\n8nSetup\
├── crates/
│   └── alos_native/
│       ├── Cargo.toml
│       └── src/
│           ├── lib.rs
│           ├── vault.rs
│           ├── bm25.rs
│           └── graph.rs
├── alos/
│   └── memory/
│       ├── obsidian_vault.py   # Hybrid native/python fallback wrapper
│       ├── spec_rag.py         # Hybrid native/python fallback wrapper
│       ├── obsidian_graph.py   # Hybrid native/python fallback wrapper
│       └── vector_store.py     # Hybrid native/python fallback wrapper
├── specs/
│   └── 003-rust-native-perf/
│       ├── spec.md
│       ├── plan.md
│       └── tasks.md
└── tests/
    ├── test_obsidian_vault_brain.py
    ├── test_spec_rag.py
    └── test_rust_native_parity.py
```

**Structure Decision**: Mixed Python/Rust layout with Rust source in `crates/alos_native` and Python wrappers in `alos/memory/`.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Multi-language extension | Python regex/loop performance insufficient for 10k+ markdown files | Pure Python string manipulation cannot meet latency targets |
