# Quality Gate & Requirements Checklist: Parallel Testing & Cross-Platform QA Matrix (035)

- [x] `spec.md`, `plan.md`, `tasks.md`, and `checklists/requirements.md` initialized via SpecKit scripts under `specs/035-parallel-testing-and-qa-matrix/`.
- [x] `ADR-0019` and `ADR-0020` proposed, accepted, indexed, and verified via `uv run pyadr check-adr-repo --no-ansi`.
- [x] **FR-001**: Ephemeral port allocation (`127.0.0.1:0`) and `autouse` `ALOS_HOME` / `tmp_path` / `global_tracer` isolation verified across `tests/` and `features/`.
- [x] **FR-002**: `pytest-xdist` parallel execution (`worksteal`) + parallel `coverage.py` (`branch = true`, `parallel = true`, `coverage combine`) active in `scripts/run_pytest_clean.py`.
- [x] **FR-003**: `scripts/run_behave_parallel.py` runs `@mocked` scenarios in parallel across worker processes and serializes `@live` / `@docker_live` scenarios with JUnit/JSON output.
- [x] **FR-004**: Lazy CLI imports in `alos/cli.py` and worker-cached immutable repo scans in `tests/meta/` verified.
- [x] **FR-005**: Cross-platform `scripts/run_validation_suite.py` runs static gates concurrently and preserves `scripts/run-validation-suite.ps1` CLI compatibility.
- [x] **FR-006**: SQLite `WAL` + `busy_timeout` + `BEGIN IMMEDIATE` CAS leasing in `StickyEpochQueue` passes multi-thread and multi-process contention storms with zero double-leases.
- [x] **FR-007**: `SingleInstanceLock`, `HealthHeartbeat`, `SystemAuditLogger`, `DecisionLogger`, `TelemetryTracer`, and `FastAuditJournalWriter` pass concurrent race and atomic JSONL line checks.
- [x] **FR-008**: `@pytest.mark.contention` domain stress suite passes across queue, lock, journal, governor/spinner, and sandbox worker pools.
- [x] **FR-009**: Composable behavior markers/tags, deterministic seed flags, and JUnit XML/JSON outputs active.
- [x] **FR-010**: Cross-platform `scripts/traceability.py` passes and measured `alos/` coverage exceeds `90%` (`--cov-fail-under=90`).
- [x] **FR-011**: `Hypothesis` `fast`/`deep` profiles, `RuleBasedStateMachine` suites, parser/schema/sandbox fuzzers, and Python-vs-Rust differential fuzzing pass.
- [x] **FR-012**: Rust `crates/alos_native` `LazyLock<Regex>`, CRLF parsing, unit tests, and `proptest` property tests pass under `cargo test --no-default-features` and `cargo clippy -- -D warnings`.
- [x] **FR-013**: `cargo-mutants` and Python mutation harness (`[tool.mutmut]` + `scripts/run_python_mutants.py`) achieve `>= 85%` mutant kill rate across targeted modules.
- [x] **FR-014**: Dual-OS PID liveness, process-group termination, and sensor fallbacks verified by cross-OS contract tests.
- [x] **FR-015**: `quality-gate.yml`, `rust-ci.yml`, and `scheduled-matrix-test.yml` run on `ubuntu-latest` and `windows-latest` with 40-char SHA pins and combined coverage verification.
