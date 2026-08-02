# Feature Specification: System-Wide Architectural Refactor & Rust Core Engine Integration

- **Feature ID**: `002-rust-core-architectural-refactor`
- **Created**: 2026-08-02
- **Status**: Draft / In Progress
- **Specification Version**: 1.0.0

---

## 1. Overview & Objectives

This specification governs the system-wide architectural refactor of the **Local Autonomous Life Operating System (ALOS)**. It establishes a multi-layered hybrid architecture coupling a high-performance **Rust Native Engine (`alos_core_rs`)** compiled via `PyO3`/`maturin` with an enhanced, strictly typed Python 3.10+ application layer.

### Key Goals:
1. **Stage 1 — Test Fortification & Observability Overlay**:
   - Fortify test suites to achieve **>= 95% branch test coverage** across all existing modules before production refactoring.
   - Instrument all core engines with an OpenTelemetry-compatible tracing and metrics overlay (`alos.logs.telemetry`).
   - Snapshot AST code quality baselines (`radon mi`, `radon cc`) and benchmark performance baselines.

2. **Stage 2 — High-Performance Rust Native Core (`alos_core_rs`)**:
   - Provide zero-copy Rust acceleration for hybrid vector/BM25 search (`search`), graph traversal (`graph`), Safety Matrix rule evaluation (`safety`), and atomic audit logging (`journal`).
   - Implement a seamless Python native bridge (`alos.native`) with 100% pure-Python fallback drivers.

3. **Stage 3 — Core Architecture Refactoring**:
   - Refactor dual-loop reasoning engine, context assembly, Obsidian vault graph memory, and SQLAlchemy 2.0 ORM async session management.

4. **Stage 4 — AST Quality & Performance Verification**:
   - Enforce AST maintainability Index (**MI >= 85.0**) and Cyclomatic Complexity cap (**CC <= 7**).
   - Verify performance latency speedup SLAs (up to 50x-100x faster).

---

## 2. Functional Requirements (FR-001 through FR-015)

### Stage 1 Requirements: Test Fortification & Observability
- **`FR-001`**: The test suite MUST achieve >= 95% branch coverage before production code refactoring begins.
- **`FR-002`**: The observability module (`alos.logs.telemetry`) MUST capture execution span durations, state transitions, and error events without throwing runtime exceptions.
- **`FR-003`**: An AST metrics baseline file (`tests/quality/ast_metrics_baseline.json`) MUST capture pre-refactor cyclomatic complexity and maintainability index values.

### Stage 2 Requirements: Rust Native Engine & FFI Bridge
- **`FR-004`**: The Rust PyO3 crate `alos_core_rs` MUST compile cleanly via `maturin` and export submodules: `search`, `graph`, `safety`, and `journal`.
- **`FR-005`**: `alos_core_rs::search` MUST execute SIMD-accelerated BM25Okapi scoring and dense vector cosine similarity calculation.
- **`FR-006`**: `alos_core_rs::graph` MUST execute multi-hop graph traversal over Obsidian wikilink networks using Rust `petgraph`.
- **`FR-007`**: `alos_core_rs::safety` MUST classify risk tiers and evaluate rules deterministically without memory allocation.
- **`FR-008`**: `alos_core_rs::journal` MUST execute atomic, thread-safe JSONL audit log appends with CRC32 checksum validation.
- **`FR-009`**: The Python native bridge (`alos.native`) MUST dynamically import `alos_core_rs` when available and fall back gracefully to `alos.native.fallback` without breaking API contracts.

### Stage 3 Requirements: Core Framework Refactoring
- **`FR-010`**: `EvaluatorNode` MUST delegate risk classification and rule checking to `alos.native`, returning typed `EvaluationResult` objects.
- **`FR-011`**: `ContextAssembler` MUST support asynchronous context retrieval across Obsidian vault, vector store, and knowledge graph.
- **`FR-012`**: SQLAlchemy 2.0 ORM session management (`alos.db.session`) MUST support async context managers with automatic pooling and rollback.

### Stage 4 Requirements: Quality & Benchmark Enforcement
- **`FR-013`**: The AST anti-regression quality suite (`tests/quality/test_code_quality_ast.py`) MUST verify Maintainability Index `MI >= 85.0` and Cyclomatic Complexity `CC <= 7` across all Python source modules.
- **`FR-014`**: The performance benchmark harness (`tests/benchmarks/test_performance_benchmarks.py`) MUST verify latency speedup SLAs.
- **`FR-015`**: Architectural Decision Record `0012` MUST be created, accepted, and linked in `docs/adr/index.md` via `pyadr`.

---

## 3. Non-Functional Requirements (NFR)

- **`NFR-001` (Performance SLAs)**:
  - Hybrid RAG Search: < 2.5ms / query.
  - Graph Traversal (3-hop): < 0.8ms / traversal.
  - Safety Matrix Evaluation: < 0.15ms / eval.
  - Audit Journal Write Latency: < 0.3ms / entry.
- **`NFR-002` (Code Quality OKRs)**:
  - 100% strict type annotation coverage via `mypy --strict`.
  - 0 Sonar code smells, 0 Bandit security vulnerabilities.
- **`NFR-003` (Memory Footprint)**:
  - Maximum memory footprint < 45MB RAM for 10,000 indexed document chunks.

---

## 4. BDD Acceptance Criteria (Gherkin Scenarios)

```gherkin
Feature: System-Wide Architectural Refactor & Rust Core Engine Integration

  Scenario: Stage 1 Observability & Telemetry Span Tracking
    Given an initialized ALOS telemetry tracer
    When an execution span is executed around ContextAssembler
    Then the telemetry tracer records start time, end time, and duration
    And the span context is correctly closed without throwing errors

  Scenario: Native Rust Search Acceleration with Python Fallback
    Given a dataset of document chunks and query vector
    When hybrid search is invoked via alos.native
    Then the native Rust search engine processes the query in < 2.5ms
    And returning identical top-k rankings as the pure-Python fallback implementation

  Scenario: AST Anti-Regression Quality Gate Enforcement
    Given the Python source modules in alos/
    When the AST quality test suite is executed
    Then every function satisfies Cyclomatic Complexity CC <= 7
    And every module satisfies Maintainability Index MI >= 85.0
```
