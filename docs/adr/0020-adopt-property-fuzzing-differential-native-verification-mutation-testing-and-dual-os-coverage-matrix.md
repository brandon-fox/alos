# Adopt Property Fuzzing Differential Native Verification Mutation Testing and Dual OS Coverage Matrix

* Status: accepted
* Deciders: Brandon Fox
* Date: 2026-11-23

Technical Story: `specs/035-parallel-testing-and-qa-matrix/spec.md`

## Context and Problem Statement

Example-based unit tests and Ubuntu-only PR CI left subtle edge cases unverified: Python fallback vs. Rust `alos_native` behavioral drift (e.g., `FallbackBM25Indexer` substring scoring vs. Rust Okapi BM25, CRLF frontmatter handling), untested Rust arithmetic/branch mutants in `crates/alos_native`, POSIX `fork()` incompatibilities when running `mutmut` on Windows developer workstations, and uncombined OS-specific coverage across Windows (`win32` NVML/Win32 APIs, `taskkill`) and Linux (`POSIX` `killpg`, `/proc`). How do we establish continuous property fuzzing, mutation kill-rate verification, and unified Linux + Windows coverage without slowing down local inner loops?

## Decision Drivers

* **Algorithmic & State-Machine Invariants**: Prove `StickyEpochQueue`, `HostGovernor`, `SingleInstanceLock`, parsers, and Python/Rust bridges hold invariants across thousands of generated inputs and state transitions.
* **Cross-Platform Mutation Testing**: Support `cargo-mutants` for Rust on Linux/Windows, `mutmut` config for Linux, and a zero-`fork()` cross-platform Python AST mutation runner (`scripts/run_python_mutants.py`) runnable natively on Windows and Linux.
* **True Linux + Windows Parity**: Run tests natively on both `ubuntu-latest` and `windows-latest` across Python 3.11–3.13 and aggregate per-OS `.coverage` artifacts into a unified report via `[tool.coverage.paths]`.

## Considered Options

* Option 1: Tiered `Hypothesis` profiles (`fast`/`deep`) + Rust `proptest` + `cargo-mutants` + `mutmut`/cross-platform AST mutator + dual-OS GitHub Actions coverage combination
* Option 2: Nightly-only Linux fuzzing and `mutmut` without Windows execution or Rust `proptest`
* Option 3: Line-coverage thresholds only without property-based or mutation testing

## Decision Outcome

Chosen option: "Option 1: Tiered `Hypothesis` profiles (`fast`/`deep`) + Rust `proptest` + `cargo-mutants` + `mutmut`/cross-platform AST mutator + dual-OS GitHub Actions coverage combination", because tiered profiles keep PR/pre-commit deterministic and sub-second (`fast`, `derandomize=True`) while allowing deep exploration in CI, and cross-platform AST mutation + `coverage combine` eliminate Windows/Linux blind spots.

### Positive Consequences

* Differential fuzzing guarantees 1:1 behavioral parity between `alos.native` Rust extensions and pure-Python fallbacks.
* `cargo-mutants` and Python AST mutation verification expose weak assertions and surviving boundary mutants across both languages.
* Unified `ubuntu-latest` + `windows-latest` CI jobs verify both POSIX and Win32 code paths on every pull request and scheduled matrix run.

### Negative Consequences

* Dual-OS CI jobs consume additional runner minutes, mitigated by `uv` caching, Rust caching, and parallel `pytest-xdist` execution.

## Links

* Refines [ADR-0012](0012-use-pyo3-and-maturin-for-rust-native-performance-extensions.md)
* Refines [ADR-0013](0013-adopt-rust-native-core-engine-and-pre-refactor-test-fortification-architecture.md)
* Refines [ADR-0019](0019-adopt-ephemeral-port-isolation-parallel-test-orchestration-and-sqlite-contention-hardening.md)
