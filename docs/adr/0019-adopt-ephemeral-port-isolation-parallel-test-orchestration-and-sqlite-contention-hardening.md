# Adopt Ephemeral Port Isolation Parallel Test Orchestration and SQLite Contention Hardening

* Status: accepted
* Deciders: Brandon Fox
* Date: 2026-11-23

Technical Story: `specs/035-parallel-testing-and-qa-matrix/spec.md`

## Context and Problem Statement

ALOS test execution previously ran sequentially (~28.5s excluding live GPU runs on a 32-core workstation), suffered from hardcoded localhost ports (`11435`–`11499`), cold CLI subprocess imports (`crewai` loaded eagerly on every `alos` invocation), unisolated global state (`global_tracer`, default `logs/` paths), SQLite `DEFERRED` transaction deadlocks (`with_for_update(skip_locked=True)` is a no-op on SQLite without WAL or `BEGIN IMMEDIATE`), `SingleInstanceLock` TOCTOU stale-lock races, and multi-syscall `writeln!` JSONL appends. How should ALOS saturate multi-core CPU/I/O safely across Unit, BDD, Spec/Meta, Domain, and Rust suites while hardening runtime concurrency boundaries against parallel contention?

## Decision Drivers

* **Maximum Multi-Core Throughput**: Saturate available CPU cores across `pytest` (`pytest-xdist` `worksteal`), `behave` (`@mocked` worker pool), `cargo test` / `cargo nextest`, and static analysis gates (`ruff`, `mypy`, `bandit`, `pyadr`).
* **Zero Cross-Worker Flakiness**: Guarantee per-worker/per-test ephemeral ports (`127.0.0.1:0`), isolated `ALOS_HOME` / `tmp_path` outside IDE-watched workspace directories on Windows, and hardware-serialized `@live` / `@docker` execution lanes.
* **True Concurrency Safety**: Eliminate SQLite lock-upgrade deadlocks, double-leasing, split-brain PID lock reclamation, and torn JSONL log writes under multi-thread and multi-process worker storms.
* **Accurate Parallel Coverage**: Preserve branch + line coverage enforcement via `coverage.py` parallel mode (`parallel = true`) and automatic `coverage combine`.

## Considered Options

* Option 1: `pytest-xdist` (`worksteal`) + custom cross-platform parallel `behave` runner (`scripts/run_behave_parallel.py`) + concurrent validation orchestrator (`scripts/run_validation_suite.py`) + SQLite WAL/`BEGIN IMMEDIATE` CAS + atomic file/PID locking
* Option 2: Third-party `behavex` wrapper + sequential `pytest` with process-global port offsets only
* Option 3: Keep sequential test execution and rely solely on CI job-level parallelism

## Decision Outcome

Chosen option: "Option 1: `pytest-xdist` (`worksteal`) + custom cross-platform parallel `behave` runner (`scripts/run_behave_parallel.py`) + concurrent validation orchestrator (`scripts/run_validation_suite.py`) + SQLite WAL/`BEGIN IMMEDIATE` CAS + atomic file/PID locking", because it delivers deterministic multi-core saturation on both Windows and Linux without unmaintained Behave plugin incompatibilities on Python 3.11–3.13, while fixing genuine production concurrency races in `StickyEpochQueue`, `SingleInstanceLock`, and audit journals.

### Positive Consequences

* Parallelizes unit, `pytest-bdd`, meta, domain, and `@mocked` `behave` scenarios safely while keeping `@live` RTX/Ollama scenarios serialized in a dedicated hardware lane.
* `DatabaseManager` configures SQLite `WAL` mode + `busy_timeout`, and `StickyEpochQueue.lease_next` uses `BEGIN IMMEDIATE` + atomic compare-and-swap updates to guarantee zero double-leases under multi-process contention.
* Lazy CLI subcommand imports eliminate >1s cold import overhead on lightweight runtime commands (`bootstrap`, `doctor`, `status`, `enqueue`, `tick`, `daemon`, `ledger`).

### Negative Consequences

* Tests that mutate environment variables or filesystem state must strictly respect `tmp_path` and `monkeypatch` (enforced automatically via `tests/conftest.py`).
* Parallel coverage produces `.coverage.<host>.<pid>.<rand>` shards requiring `coverage combine` prior to reporting.

## Links

* Refines [ADR-0015](0015-adopt-preemptible-host-governor-and-sticky-model-epoch-queue.md)
* Refines [ADR-0018](0018-adopt-dual-mode-portable-wheel-and-hardened-container-production-runtime.md)
