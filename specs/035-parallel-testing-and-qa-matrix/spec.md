# Feature Specification: High-Velocity Parallel Testing, Contention Hardening, and Cross-Platform QA Matrix

**Feature Branch**: `feat/parallel-testing-and-qa-matrix`
**Created**: 2026-11-23
**Status**: Active
**Architecture Decisions**: [ADR-0019](../../docs/adr/0019-adopt-ephemeral-port-isolation-parallel-test-orchestration-and-sqlite-contention-hardening.md), [ADR-0020](../../docs/adr/0020-adopt-property-fuzzing-differential-native-verification-mutation-testing-and-dual-os-coverage-matrix.md)

---

## Intent

Maximize local and CI verification velocity across Unit, Behavior (`pytest-bdd` + `behave`), Spec/Meta, Domain, and Rust (`crates/alos_native`) suites by saturating multi-core CPU/I/O safely in parallel, hardening ALOS's stateful runtime boundaries against multi-thread/multi-process contention, and expanding QA rigor through property/stateful/differential fuzzing, Python + Rust mutation testing, and unified Linux + Windows coverage aggregation.

---

## User Stories

1. **As an ALOS developer on a multi-core Windows or Linux workstation**, I want `pytest`, `@mocked` `behave`, `cargo test`, and static quality gates to execute concurrently across CPU cores with zero port, file, lock, or env collisions so full pre-handback verification finishes in seconds rather than serial minutes.
2. **As a systems engineer operating local swarm workers**, I want `StickyEpochQueue`, `SingleInstanceLock`, `HealthHeartbeat`, `HostGovernor`, `ModelSpinner`, `SystemAuditLogger`, `DecisionLogger`, and `alos_native` journal writers proven under deliberate multi-thread and multi-process contention storms so no job is double-leased, deadlocked, or torn in production.
3. **As a release maintainer**, I want composable BDD/pytest behavior profiles, Hypothesis + `proptest` fuzzing, Python-vs-Rust differential parity checks, `cargo-mutants` + Python mutation kill-rate verification, and combined `ubuntu-latest` + `windows-latest` CI coverage so cross-OS and algorithmic edge-case regressions cannot slip through.

---

## Functional Requirements

### Phase 1: Parallelism, Isolation & Contention Saturation
- **FR-001 (Ephemeral Port & Resource Isolation)**: Every unit test, `pytest-bdd` scenario, and `behave` scenario MUST use OS-assigned ephemeral ports (`127.0.0.1:0` via `allocate_free_port()`) rather than shared hardcoded ports (`11435`–`11499`), isolated per-test `ALOS_HOME` / `tmp_path` directories, isolated SQLite databases, and automatic reset of module singletons (`global_tracer`).
- **FR-002 (Parallel Pytest & Parallel Coverage)**: `pyproject.toml` and `scripts/run_pytest_clean.py` MUST support `pytest-xdist` parallel execution (`-n auto --dist worksteal`), isolate Windows `--basetemp` outside IDE-watched folders, group hardware-exclusive `@pytest.mark.docker` tests safely via `xdist_group`, and combine parallel `.coverage.*` shards (`parallel = true`) before enforcing line + branch coverage floors.
- **FR-003 (Parallel Cross-Platform Behave Runner)**: `scripts/run_behave_parallel.py` MUST fan out `@mocked` Behave scenarios/features concurrently across worker processes on Windows and Linux with isolated `ALOS_HOME` and temp directories, optional parallel `coverage.py` collection, unified console + JUnit XML + JSON summaries, and hardware-serialized execution for `@live` / `@docker_live` scenarios.
- **FR-004 (Fast CLI Lazy Imports & Spec/Meta Caching)**: `alos/cli.py` MUST lazy-import heavy orchestration dependencies (`crewai`, `ALOSStateGraph`, SpecKit archivers) only for subcommands that invoke them, and meta-tests (`tests/meta/`) MUST cache immutable AST/file scans per worker without weakening assertions.
- **FR-005 (Cross-Platform Concurrent Validation Orchestrator)**: `scripts/run_validation_suite.py` (wrapped transparently by `scripts/run-validation-suite.ps1`) MUST execute independent static gates (`uv lock --check`, `ruff format`, `ruff check`, `mypy`, `bandit`, `pyadr`, and optional `cargo fmt`/`clippy`/`test`) concurrently alongside parallel test suites on both Linux and Windows.
- **FR-006 (SQLite Queue Contention Hardening)**: `DatabaseManager` MUST configure SQLite connections with `PRAGMA journal_mode=WAL`, `PRAGMA synchronous=NORMAL`, and `PRAGMA busy_timeout=30000`, and `StickyEpochQueue.lease_next()` MUST use `BEGIN IMMEDIATE` + atomic compare-and-swap updates (`WHERE state IN ('queued', 'preempted')`) and thread-safe epoch/delta locks so concurrent multi-thread and multi-process workers never double-lease or deadlock.
- **FR-007 (Lock, Heartbeat & Journal Contention Hardening)**: `SingleInstanceLock` MUST eliminate partial-write and stale-PID reclamation TOCTOU races across threads and subprocesses; `HealthHeartbeat` MUST write unique per-writer temp files before atomic replacement; `SystemAuditLogger`, `DecisionLogger`, `TelemetryTracer`, `FallbackAuditJournalWriter`, and Rust `FastAuditJournalWriter` MUST serialize concurrent writes into atomic single-syscall JSONL lines without torn or interleaved records.
- **FR-008 (Domain Concurrency & Contention Stress Suite)**: `tests/test_contention_stress.py` (`@pytest.mark.contention`) MUST stress-test `StickyEpochQueue` multi-thread/multi-process worker storms (including 3-open-PR merge caps and lease expiry reclamation), `SingleInstanceLock` race storms, concurrent Python/Rust JSONL appends, `HostGovernor`/`ModelSpinner` concurrent ticks + eviction races, and multi-worker `alos.swarm.sandbox.run_plan` execution.

### Phase 2: Behavior Profiles, Coverage Expansion, Fuzzing, Mutation & Dual-OS Matrix
- **FR-009 (Composable Behavior Profiles & Tag Taxonomy)**: `pyproject.toml` and test runners MUST support composable tags/markers (`mocked`, `live`, `docker_live`, `contention`, `fuzz`, `smoke`, `linux_only`, `windows_only`, `platform_agnostic`), deterministic seed replay, JUnit XML + JSON reporting, and `--require-live` / `--skip-live` CI controls.
- **FR-010 (Expanded Module Coverage & Requirement Traceability)**: Automated unit, domain, `pytest-bdd`, and `behave` tests MUST close coverage gaps across `alos/` (`cli`, `runtime`, `memory`, `native`, `swarm`, `integrations`, `db`, `core`, `crews`), raising measured coverage to `>= 90%` (`--cov-fail-under=90`), and `scripts/traceability.py` (invoked by `scripts/traceability.ps1`) MUST verify `FR-XXX` requirement traceability cross-platform.
- **FR-011 (Python Property, Stateful & Differential Fuzzing)**: `tests/` MUST integrate `Hypothesis` with `fast` (`derandomize=True`) and `deep` profiles in `tests/conftest.py`, covering stateful state machines (`StickyEpochQueue`, `HostGovernor`, `SingleInstanceLock`), adversarial parser/schema/sandbox fuzzing, and 1:1 Python-vs-Rust differential fuzzing (`alos.native` vs `alos_native`, including exact Okapi BM25 parity in `FallbackBM25Indexer`).
- **FR-012 (Rust `proptest` Property Suite & Regex Optimization)**: `crates/alos_native` MUST precompile vault regexes via `std::sync::LazyLock` for lock-free `rayon` parallel parsing, handle CRLF/LF frontmatter consistently, and validate `bm25.rs`, `graph.rs`, `journal.rs`, `safety.rs`, and `vault.rs` with unit + `proptest` suites for panic-freedom, UTF-8 boundary safety, and scoring determinism.
- **FR-013 (Rust & Cross-Platform Python Mutation Testing)**: `crates/alos_native` MUST be configured and verified with `cargo-mutants`, and Python MUST provide both `[tool.mutmut]` configuration for Linux and a zero-`fork()` cross-platform AST mutation runner (`scripts/run_python_mutants.py`) targeting core domain modules on Windows and Linux, with targeted tests remediating surviving mutants.
- **FR-014 (Cross-Platform OS Runtime Parity)**: OS-specific paths in `alos/runtime.py` (`_is_windows_pid_alive` `ERROR_ACCESS_DENIED` handling vs POSIX `os.kill(pid, 0)`), `alos/swarm/governor.py` & `dispatcher.py` (POSIX process-group `start_new_session` + `os.killpg` + `SIGKILL` escalation vs Windows `taskkill /T /F`), and `alos/swarm/sensors.py` (Linux `/proc/meminfo` & `ps` process list parity) MUST behave consistently across Linux and Windows and be verified by cross-OS contract tests.
- **FR-015 (Dual-OS Linux + Windows CI Matrix & Combined Coverage)**: `.github/workflows/quality-gate.yml`, `.github/workflows/rust-ci.yml`, and `.github/workflows/scheduled-matrix-test.yml` MUST execute on both `ubuntu-latest` and `windows-latest` using 40-char SHA-pinned actions, upload per-OS `.coverage` artifacts, combine them via `[tool.coverage.paths]`, and enforce strict coverage floors.

---

## Non-Functional Requirements

- **NFR-001 (Parallel Speedup)**: Full local non-live validation wall-clock duration MUST improve measurably over the 28.46s sequential baseline while executing significantly more tests (contention, fuzz, OS-parity, and expanded coverage).
- **NFR-002 (Zero Flakiness)**: Repeated multi-worker parallel soak runs (`pytest -n auto` and parallel `@mocked` `behave`) MUST achieve a 0% flake rate with zero `WinError 5` teardown errors or port collisions.
- **NFR-003 (Complexity & Static Quality)**: Every function across `alos/` MUST maintain AST Cyclomatic Complexity `CC <= 12` and pass `ruff`, `mypy`, and `bandit` with zero undocumented suppressions.
- **NFR-004 (Action SHA Pinning)**: Every external GitHub Action in `.github/workflows/` MUST use a verified 40-character commit SHA with an inline version comment.
- **NFR-005 (Local-First Determinism)**: All mocked, contention, property, and mutation suites MUST execute 100% offline without external cloud APIs.
- **NFR-006 (Mutant Kill Rate)**: Targeted Rust (`cargo-mutants`) and Python domain mutation suites MUST achieve `>= 85%` mutant kill rate across audited core logic.

---

## Acceptance Scenarios

```gherkin
Feature: High-Velocity Parallel Testing, Contention Hardening, and Cross-Platform QA Matrix

  Scenario: Parallel pytest and behave suites saturate CPU cores with zero port or file collisions
    Given isolated worker environments and ephemeral localhost port allocation
    When parallel pytest (-n auto) and parallel mocked behave execute concurrently with coverage enabled
    Then all unit, meta, BDD, domain, contention, and fast fuzz tests pass with combined coverage >= 90%

  Scenario: Multi-worker contention storms preserve strict queue, lock, and journal invariants
    Given an SQLite StickyEpochQueue in WAL mode, a SingleInstanceLock, and an audit journal
    When concurrent threads and subprocesses race to lease jobs, acquire locks, and append JSONL records
    Then zero jobs are double-leased, exactly one lock holder wins per epoch, and every JSONL line parses cleanly

  Scenario: Differential fuzzing and cross-OS contract suites prove Python, Rust, Linux, and Windows parity
    Given fast Hypothesis profiles, Rust proptest suites, and cross-OS runtime contract tests
    When arbitrary inputs exercise BM25, vault parsing, safety evaluation, PID liveness, and process-tree eviction
    Then Python fallbacks match Rust native outputs and POSIX/Windows branches satisfy identical safety contracts
```
