# Architectural Plan: System-Wide Refactor & Rust Core Engine Integration

- **Feature ID**: `002-rust-core-architectural-refactor`
- **Created**: 2026-08-02
- **Status**: Draft / In Progress

---

## 1. High-Level Architecture & Component Blueprint

```mermaid
graph TD
    subgraph Python Application Layer (alos/)
        CA[alos.core.context_assembler]
        PN[alos.core.planner]
        EN[alos.core.evaluator]
        DL[alos.logs.decision_log]
        Tel[alos.logs.telemetry]
    end

    subgraph Native Bridge Layer (alos/native/)
        Bridge[alos.native.bridge]
        FB[alos.native.fallback]
    end

    subgraph Rust Native Engine (crates/alos_core_rs)
        Search[alos_core_rs::search]
        Graph[alos_core_rs::graph]
        Safety[alos_core_rs::safety]
        Journal[alos_core_rs::journal]
    end

    CA --> Tel
    EN --> Bridge
    DL --> Bridge
    Bridge -->|PyO3 FFI| Search
    Bridge -->|PyO3 FFI| Graph
    Bridge -->|PyO3 FFI| Safety
    Bridge -->|PyO3 FFI| Journal
    Bridge -.->|Fallback| FB
```

---

## 2. Module & Data Layout

### Rust Crate Structure (`crates/alos_core_rs/`)
- `Cargo.toml`: Cargo workspace & PyO3 maturin configuration.
- `src/lib.rs`: PyO3 module initialization (`#[pymodule]`).
- `src/search.rs`: SIMD BM25 & cosine vector math engine.
- `src/graph.rs`: `petgraph::DiGraph` for Obsidian link traversal.
- `src/safety.rs`: Zero-allocation Safety Matrix rule evaluator.
- `src/journal.rs`: Atomic JSONL audit writer with CRC32 verification.

### Python Native Bridge (`alos/native/`)
- `__init__.py`: Dynamic module binder (`alos_core_rs` vs fallback).
- `bridge.py`: Unified API wrapper functions.
- `fallback.py`: Pure-Python fallback drivers guaranteeing 100% test compatibility.

### Observability & Telemetry (`alos/logs/telemetry.py`)
- `SpanContext`: Dataclass tracking operation start time, duration, tags, and status.
- `TelemetryTracer`: Thread-safe span collector and metrics reporter.

---

## 3. AST Quality & Performance SLA Requirements

- Maintainability Index: **MI >= 85.0** (`radon mi`)
- Cyclomatic Complexity: **CC <= 7** (`radon cc`)
- Strict Typing: **100% Coverage** (`mypy --strict`)
- Hybrid Search Latency: **< 2.5ms**
- Graph Traversal Latency: **< 0.8ms**
- Safety Evaluation Latency: **< 0.15ms**
- Audit Write Latency: **< 0.3ms**
