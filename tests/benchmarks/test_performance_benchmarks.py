"""Performance Benchmark Test Suite.

Spec: specs/002-rust-core-architectural-refactor/spec.md (NFR-001)
"""

from __future__ import annotations

import time

from tests.benchmarks.benchmark_reporter import BenchmarkReporter


def test_benchmark_harness_search_simulation() -> None:
    """Simulate and measure baseline hybrid search latency over 100 iterations."""
    reporter = BenchmarkReporter()
    latencies: list[float] = []

    for _ in range(100):
        t0 = time.perf_counter()
        # Simulated search operation baseline
        time.sleep(0.0001)
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)

    res = reporter.record_latencies("baseline_hybrid_search", latencies)
    assert res.iterations == 100
    assert res.mean_ms > 0
    assert res.ops_per_sec > 0


def test_benchmark_harness_safety_matrix_eval_simulation() -> None:
    """Simulate and measure baseline Safety Matrix evaluation latency over 100 iterations."""
    reporter = BenchmarkReporter()
    latencies: list[float] = []

    for _ in range(100):
        t0 = time.perf_counter()
        # Simulated safety eval baseline
        time.sleep(0.00005)
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)

    res = reporter.record_latencies("baseline_safety_eval", latencies)
    assert res.iterations == 100
    assert res.mean_ms > 0
