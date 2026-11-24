# spec: 035-parallel-testing-and-qa-matrix
Feature: Parallel Contention Safety, Differential Native Parity, and OS Contracts
  As a cross-platform ALOS maintainer
  I want contention storms, native/fallback BM25 parity, and OS-specific hooks verified via composable BDD tags
  So that Linux and Windows deployments maintain identical safety and queue invariants

  @mocked @contention @smoke @platform_agnostic
  Scenario: Concurrent multi-worker StickyEpochQueue leasing preserves strict 1-to-1 job ownership
    Given a WAL-mode SQLite StickyEpochQueue with 20 queued jobs across 2 tiers
    When 6 concurrent threads lease and complete all runnable jobs
    Then every job transitions to "succeeded" with zero duplicate leases

  @mocked @smoke @platform_agnostic
  Scenario: FallbackBM25Indexer and SafetyEvaluator match canonical Okapi BM25 and fail-safe HIGH rules
    Given a FallbackBM25Indexer loaded with "Safety Matrix" spec and "Daily Journal" vault chunks
    When I search BM25 for "safety" with top_k 2
    Then the top BM25 hit is "Safety Matrix" with positive Okapi score
    And classifying an unknown tool action returns fail-safe tier "HIGH"

  @mocked @windows_only
  Scenario: Windows host PID liveness and commit memory telemetry return valid Win32 readings
    Given the current Windows host process PID
    Then is_pid_alive reports True for the current PID and positive free commit MiB

  @mocked @linux_only
  Scenario: Linux host PID liveness and /proc/meminfo parser return valid POSIX readings
    Given the current Linux host process PID and a synthetic meminfo file with 8388608 kB MemAvailable
    Then is_pid_alive reports True for the current PID and 8192 MiB available memory
