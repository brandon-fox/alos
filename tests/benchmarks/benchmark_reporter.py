"""Performance Benchmark Reporter Module.

Spec: specs/002-rust-core-architectural-refactor/spec.md (NFR-001)
"""

from __future__ import annotations

import statistics
from typing import Any

from pydantic import BaseModel, Field


class BenchmarkResult(BaseModel):
    """Execution results for a single benchmark scenario."""

    benchmark_name: str
    iterations: int
    mean_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    ops_per_sec: float
    tags: dict[str, Any] = Field(default_factory=dict)


class BenchmarkReporter:
    """Aggregates and formats latency statistics for before/after comparison."""

    def __init__(self) -> None:
        self._results: list[BenchmarkResult] = []

    def record_latencies(
        self, name: str, latencies_ms: list[float], tags: dict[str, Any] | None = None
    ) -> BenchmarkResult:
        """Calculate statistics from a list of latency measurements in ms."""
        if not latencies_ms:
            raise ValueError("latencies_ms list cannot be empty")

        sorted_latencies = sorted(latencies_ms)
        n = len(sorted_latencies)
        mean_val = statistics.mean(sorted_latencies)
        p50_idx = int(0.50 * n)
        p95_idx = int(0.95 * n)
        p99_idx = int(0.99 * n)

        p50_val = sorted_latencies[min(p50_idx, n - 1)]
        p95_val = sorted_latencies[min(p95_idx, n - 1)]
        p99_val = sorted_latencies[min(p99_idx, n - 1)]
        ops_sec = (1000.0 / mean_val) if mean_val > 0 else 0.0

        result = BenchmarkResult(
            benchmark_name=name,
            iterations=n,
            mean_ms=round(mean_val, 4),
            p50_ms=round(p50_val, 4),
            p95_ms=round(p95_val, 4),
            p99_ms=round(p99_val, 4),
            ops_per_sec=round(ops_sec, 2),
            tags=tags or {},
        )
        self._results.append(result)
        return result

    def get_results(self) -> list[BenchmarkResult]:
        """Return recorded benchmark results."""
        return list(self._results)
