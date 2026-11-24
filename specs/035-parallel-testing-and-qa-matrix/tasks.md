# Implementation Tasks: High-Velocity Parallel Testing, Contention Hardening, and Cross-Platform QA Matrix

**Spec**: [`specs/035-parallel-testing-and-qa-matrix/spec.md`](spec.md)
**Plan**: [`specs/035-parallel-testing-and-qa-matrix/plan.md`](plan.md)

---

## Phase 1: Parallelism, Isolation, Speed & Contention Hardening

- [x] **Task 1**: Initialize SpecKit `035-parallel-testing-and-qa-matrix`, record baseline timings, and accept `ADR-0019` and `ADR-0020` via `pyadr`. (`FR-001`..`FR-015`)
- [x] **Task 2**: Write failing isolation & concurrency tests (`tests/test_contention_stress.py`) exposing SQLite `StickyEpochQueue` double-lease/lock-upgrade races, `SingleInstanceLock` stale-reclaim races, concurrent JSONL append tearing, and `TelemetryTracer` thread-safety gaps (RED). (`FR-001`, `FR-006`, `FR-007`, `FR-008`)
- [x] **Task 3**: Implement ephemeral port allocation (`allocate_free_port`), SQLite WAL + `BEGIN IMMEDIATE` CAS queue leasing, race-free `SingleInstanceLock` & `HealthHeartbeat`, thread/process-safe JSONL writers (Python + Rust `journal.rs`), lazy `alos/cli.py` imports, and `tests/conftest.py` env/singleton isolation; eliminate all hardcoded test ports and verify GREEN. (`FR-001`, `FR-004`, `FR-006`, `FR-007`, `FR-008`)
- [x] **Task 4**: Add `pytest-xdist` + `hypothesis` to `pyproject.toml`/`uv.lock`, upgrade `scripts/run_pytest_clean.py` for parallel worker tuning + parallel `coverage combine`, implement `scripts/run_behave_parallel.py` and `scripts/run_validation_suite.py` (wired into `scripts/run-validation-suite.ps1` and `.pre-commit-config.yaml`), optimize `tests/meta/` caching, and pass Phase 1 multi-iteration zero-flake benchmark gate. (`FR-002`, `FR-003`, `FR-004`, `FR-005`, `NFR-001`, `NFR-002`)

## Phase 2: Behavior Profiles, Fuzzing, Mutation Testing & Cross-Platform Matrix

- [x] **Task 5**: Configure composable `pytest`/`behave` behavior profiles and markers (`@mocked`, `@live`, `@docker_live`, `@contention`, `@fuzz`, `@smoke`, `@linux_only`, `@windows_only`, `@platform_agnostic`), implement cross-platform `scripts/traceability.py`, and expand unit + BDD coverage across `alos/` above 90%. (`FR-009`, `FR-010`)
- [x] **Task 6**: Align Python-vs-Rust behavioral parity (`FallbackBM25Indexer` Okapi BM25, `bm25.rs` default `top_k=5`, `vault.rs` `LazyLock<Regex>` + CRLF frontmatter) and implement Python `Hypothesis` property/stateful/differential fuzz suites + Rust `proptest` suites across `crates/alos_native`. (`FR-011`, `FR-012`)
- [x] **Task 7**: Configure and run `cargo-mutants` on `crates/alos_native` and Python mutation testing (`[tool.mutmut]` + cross-platform `scripts/run_python_mutants.py`), adding targeted tests to remediate surviving mutants (`>= 85%` kill rate). (`FR-013`, `NFR-006`)
- [ ] **Task 8**: Harden Linux/Windows OS-specific parity (`is_pid_alive`, POSIX `killpg` process-tree termination, Linux sensor fallbacks) with cross-OS contract tests, configure `[tool.coverage.paths]` and dual-OS (`ubuntu-latest` + `windows-latest`) GitHub Actions workflows (`quality-gate.yml`, `rust-ci.yml`, `scheduled-matrix-test.yml`), run full validation + soak checks, update Spec 035 metrics, push, and open PR. (`FR-014`, `FR-015`, `NFR-001`..`NFR-006`)
