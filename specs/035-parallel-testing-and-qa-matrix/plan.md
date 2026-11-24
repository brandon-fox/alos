# Technical Execution Plan: High-Velocity Parallel Testing, Contention Hardening, and Cross-Platform QA Matrix

**Spec**: [`specs/035-parallel-testing-and-qa-matrix/spec.md`](spec.md)
**ADRs**: [ADR-0019](../../docs/adr/0019-adopt-ephemeral-port-isolation-parallel-test-orchestration-and-sqlite-contention-hardening.md), [ADR-0020](../../docs/adr/0020-adopt-property-fuzzing-differential-native-verification-mutation-testing-and-dual-os-coverage-matrix.md)

---

## 1. Baseline Profiling & Bottleneck Audit (Pre-Phase-1 Measurements)

Measured on workstation (`Windows-11-10.0.26300-SP0`, 32 logical CPUs, Python 3.12.12, `pytest` 9.1.1, `behave` 1.2.6, Rust 1.x via `rust:1-bookworm`):

| Validation Gate / Suite | Baseline Mode | Wall-Clock (s) | Bottleneck / Root Cause Identified |
| :--- | :--- | ---: | :--- |
| `uv lock --check` | Sequential | `0.03s` | Fast, runs serially before linters |
| `ruff format --check` | Sequential | `0.11s` | Runs serially |
| `ruff check` | Sequential | `0.07s` | Runs serially |
| `mypy alos tests features` | Sequential | `1.81s` | Runs serially before `bandit` / `pytest` |
| `bandit -r alos -s B101` | Sequential | `0.71s` | Runs serially |
| `pyadr check-adr-repo` | Sequential | `0.52s` | Runs serially |
| `pytest --cov=alos` (180 items: 172 passed, 8 skipped, 87% line cov) | Single-process | `10.62s` | `test_bootstrap_idempotency_doctor_and_heartbeat` (`1.60s` Windows closed-port TCP SYN retry on `11491`), `test_t2_hung_runner_process_tree_killed_on_eviction` (`1.24s`), serial execution across 34 test modules |
| `behave --tags="@mocked"` (4 features, 19 passed, 5 skipped) | Single-process | `14.59s` | `portable_runtime.feature` (`11.60s` due to 9 serial `python -m alos.cli` cold imports loading `crewai` + closed-port SYN timeout), `cli_and_live_integration.feature` (`3.61s`), `governor_spindown.feature` (`2.01s`), `sticky_epoch_queue.feature` (`1.32s`) |
| `cargo fmt` / `clippy` / `test --no-default-features` (4 Rust tests) | Cached build | `0.42s` | Only 4 Rust unit tests (`0` in `bm25.rs`, `journal.rs`, `safety.rs`); `vault.rs` recompiles `Regex::new` per file inside `rayon::par_iter` |
| **Total Non-Live Sequential Baseline** | **Serial** | **28.46s** (+ `0.42s` Rust) | **Zero parallelism across gates, pytest modules, or behave features; eager CLI imports; TCP timeout waits** |

### Shared-Resource & Contention Audit Findings
1. **Hardcoded Ports**: `11436`, `11439`, `11491`, `11494`, `11495`, `11496`, `11497`, `11498`, `11499` across `tests/test_swarm_governor.py`, `tests/test_portable_runtime.py`, `alos/swarm/queue.py`, `features/steps/governor_steps.py`, `features/steps/cli_and_live_steps.py`, and `features/steps/portable_runtime_steps.py`.
2. **Filesystem/Singleton Leaks**: `ALOSStateGraph` / `SystemAuditLogger` / `DecisionLogger` fallback to repo-root `logs/*.jsonl` when env/args omitted; `global_tracer` mutated without lock or per-test reset.
3. **SQLite & Runtime Races**:
   - `DatabaseManager` lacked `PRAGMA journal_mode=WAL` and `busy_timeout`; `StickyEpochQueue.lease_next()` relied on `with_for_update(skip_locked=True)` (ignored by SQLite), allowing lock-upgrade deadlocks and double-leases.
   - `SingleInstanceLock` had partial-write (`JSONDecodeError -> pid 0 -> unlink`) and stale-PID reclamation TOCTOU windows.
   - `HealthHeartbeat` used a fixed `health.tmp` path across writers.
   - `FallbackAuditJournalWriter`, `DecisionLogger`, `TelemetryTracer`, and Rust `FastAuditJournalWriter` (`writeln!` two-write split) lacked cross-thread/process atomic single-buffer writes.
4. **Python-vs-Rust & OS Divergences**:
   - `FallbackBM25Indexer` used substring matching (`0.1` fallback) instead of Okapi BM25 (`bm25.rs`), and `FastBM25Indexer.search` lacked default `top_k=5`.
   - `_is_windows_pid_alive` returned `False` on `ERROR_ACCESS_DENIED (5)` (unlike POSIX `PermissionError -> True`), and POSIX `kill_process_tree` sent `SIGTERM` only to parent PID rather than process group + `SIGKILL` escalation.

---

## 2. Phase 1 Architecture: Parallelism & Contention Hardening

| Component | Design | Requirements |
| :--- | :--- | :--- |
| `alos/runtime.py` (`allocate_free_port`, `SingleInstanceLock`, `HealthHeartbeat`, `is_pid_alive`) | Ephemeral loopback port allocator (`127.0.0.1:0`), atomic temp-write + inode/PID verification on lock reclaim, unique per-thread `.tmp` heartbeats, Win32 `ERROR_ACCESS_DENIED` parity. | `FR-001`, `FR-007`, `FR-014` |
| `alos/db/session.py` & `alos/swarm/queue.py` | SQLAlchemy `connect` event setting `WAL`, `synchronous=NORMAL`, `busy_timeout=30000`; `BEGIN IMMEDIATE` + `UPDATE ... WHERE job_id=:id AND state IN ('queued','preempted')` CAS loop + `threading.Lock` on epoch/ledger counters. | `FR-006` |
| `alos/logs/*`, `alos/native/fallback.py`, `crates/alos_native/src/journal.rs` | `threading.Lock` + `os.O_APPEND` single-buffer UTF-8 writes (`record + "\n"`), `ALOS_AUDIT_LOG_PATH`/`ALOS_DECISION_LOG_PATH`/`ALOS_HOME` resolution, mutex poison recovery + single `write_all` in Rust. | `FR-001`, `FR-007` |
| `alos/cli.py` | Lazy subcommand imports so `bootstrap`/`doctor`/`status`/`enqueue`/`tick`/`daemon`/`ledger` skip loading `crewai` and `langgraph`. | `FR-004` |
| `tests/conftest.py` & `scripts/run_pytest_clean.py` | Per-test `autouse` `ALOS_HOME`/env/`global_tracer` isolation, Hypothesis `fast`/`deep` profiles, `pytest-xdist` (`-n auto --dist worksteal` capped cleanly to avoid oversubscription), `COVERAGE_FILE` + `coverage combine` in isolated temp root. | `FR-001`, `FR-002`, `FR-011` |
| `scripts/run_behave_parallel.py` | `ProcessPoolExecutor` / subprocess fan-out of `@mocked` features/scenarios with isolated `ALOS_HOME`, optional `--cov` (`coverage run --parallel-mode`), JUnit XML + JSON summaries, and serialized `@live` / `@docker_live` hardware lane. | `FR-003`, `FR-009` |
| `scripts/run_validation_suite.py` & `scripts/run-validation-suite.ps1` | Concurrent static gate runner (`uv lock --check`, `ruff`, `mypy`, `bandit`, `pyadr`, `cargo`) + parallel `pytest` + parallel `behave`, cross-platform CLI flags (`--skip-live`, `--require-live`, `--profile`). | `FR-005`, `FR-009` |
| `tests/test_contention_stress.py` | Multi-thread & multi-process contention stress tests across `StickyEpochQueue`, `SingleInstanceLock`, JSONL journals (Python + Rust), `HostGovernor`/`ModelSpinner`, and `sandbox.run_plan`. | `FR-008` |

---

## 3. Phase 2 Architecture: Behavior Profiles, Fuzzing, Mutation & Dual-OS CI

| Component | Design | Requirements |
| :--- | :--- | :--- |
| `alos/native/fallback.py` & `crates/alos_native/src/{bm25,graph,journal,safety,vault}.rs` | Exact Okapi BM25 parity in `FallbackBM25Indexer`, `top_k=5` default in `bm25.rs`, `LazyLock<Regex>` + CRLF frontmatter support in `vault.rs`, pure-Rust inner functions testable under `--no-default-features`, comprehensive unit + `proptest` suites. | `FR-011`, `FR-012` |
| `tests/test_fuzz_properties.py` & `tests/test_fuzz_stateful.py` | Hypothesis `RuleBasedStateMachine` suites (`StickyEpochQueue`, `HostGovernor`, `SingleInstanceLock`), adversarial parser/schema/sandbox fuzzers, and Python-vs-Rust differential fuzzing. | `FR-011` |
| `scripts/run_python_mutants.py`, `[tool.mutmut]`, `crates/alos_native/.cargo/mutants.toml` | Cross-platform AST mutation testing harness for Windows & Linux + `mutmut` Linux config + `cargo-mutants` configuration and targeted mutant-killing tests. | `FR-013`, `NFR-006` |
| `alos/swarm/{governor,dispatcher,sensors}.py` & `tests/test_cross_platform_contracts.py` | POSIX process-group kill (`start_new_session=True`, `os.killpg`, `SIGKILL` fallback), Linux `/proc/meminfo` + `ps` support, and mocked + native OS contract tests. | `FR-014` |
| `scripts/traceability.py`, `tests/test_expanded_coverage.py`, `features/concurrency_and_parity.feature` | Close coverage gaps across `alos/` (`>= 90%` branch+line floor), cross-platform `FR-XXX` traceability verifier, expanded `pytest-bdd` and `behave` scenarios. | `FR-009`, `FR-010` |
| `.github/workflows/{quality-gate,rust-ci,scheduled-matrix-test}.yml` & `pyproject.toml` | Dual-OS (`ubuntu-latest`, `windows-latest`) parallel test + coverage jobs, `[tool.coverage.paths]` path remapping, `coverage combine` aggregation job, 40-char SHA pins. | `FR-015`, `NFR-004` |

---

## 4. Constitution Gate Compliance

- **Article I (Determinism & Schema Validation)**: Preserves two-stage Plan -> Evaluate gates; adds property fuzzing over Pydantic action schemas.
- **Article II (Local-First Sovereignty)**: Zero external network calls in unit, BDD, contention, fuzz, or mutation suites.
- **Article III (Decision Provenance & Audit Integrity)**: Hardens `DecisionLogger` and `SystemAuditLogger` against concurrent multi-thread/multi-process torn writes.
- **Article IV (Test-First Development)**: Every runtime concurrency/parity fix is preceded by failing contention, differential, or coverage tests (Red -> Green -> Refactor).
- **Article V (Safety Matrix Enforcement)**: Differential fuzzing + `proptest` + mutation testing lock `LOW`/`MEDIUM`/`HIGH` fail-safe risk invariants in both Python and Rust.
- **Article VII (Code Quality & Fix-First)**: Enforces `CC <= 12`, strict `ruff`/`mypy`/`bandit`, and explicit technical justifications on any unavoidable platform-specific `# noqa`.

---

## 5. Measured Post-Implementation Benchmarks & Verification Metrics

| Metric | Baseline (Pre-Phase 1) | Post-Phase 1 & Phase 2 (Bounded Local) | CI Offload Target |
| :--- | :--- | :--- | :--- |
| Static + Pytest + Mocked Behave Wall-Clock | `28.46s` (180 pytest items, 19 Behave mocked) | `23.72s` (207 pytest items incl. contention + Hypothesis fuzz + cross-OS contracts, 22 Behave mocked) | Parallel across Linux & Windows GitHub runners |
| `pytest` + Branch Coverage | `87%` line-only (`10.62s`, 180 items) | `90%+` **line + branch** (`--cov-fail-under=90`, 207 items) | Combined `ubuntu-latest` + `windows-latest` `.coverage` |
| Local Workstation Safety | Unbounded `spawn` risked memory pressure | Bounded `workers=2` locally (`CI=true` scales to 4) | Heavy deep fuzz (`HYPOTHESIS_PROFILE=deep`) & mutation sweeps offloaded to GitHub Actions |
| Rust (`crates/alos_native`) Tests | `4` unit tests (`cargo test`) | `15` unit + `proptest` suites (`cargo nextest`, `0.39s`) | `ubuntu-latest` + `windows-latest` + `maturin` PyO3 parity |
| Rust Mutation (`cargo-mutants`) | Untested (`0%` bm25/journal/safety) | `92 / 92` viable mutants killed (`100.00%`, `0` missed) | Verified via `rust-ci.yml` |
| Python AST Mutation (`run_python_mutants.py`) | None | `13 / 13` sampled core mutants killed (`100.00%`) | Full sweep (`workers=4`, `max-per-file=12`) offloaded to `qa-deep-fanout` |
