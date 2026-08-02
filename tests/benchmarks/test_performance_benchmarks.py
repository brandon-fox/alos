"""Performance Benchmark Test Suite measuring Pure-Python vs Native Bridge Latency & Throughput.

Spec: specs/003-rust-core-architectural-refactor/spec.md (NFR-001)
"""

from __future__ import annotations

import time
from pathlib import Path

from alos.native import get_bm25_indexer, get_journal_writer, get_safety_evaluator
from tests.benchmarks.benchmark_reporter import BenchmarkReporter


def test_benchmark_harness_search_simulation() -> None:
    """Benchmark BM25 search indexer over 1,000 iterations."""
    reporter = BenchmarkReporter()
    indexer = get_bm25_indexer()
    indexer.add_chunk(
        header="Architecture ADR",
        file_name="0013-adr.md",
        file_path="/docs/adr/0013.md",
        source_type="adr",
        content="Rust native core engine architecture decision record for ALOS system refactor",
    )

    latencies: list[float] = []
    for _ in range(1000):
        t0 = time.perf_counter()
        indexer.search("architecture", top_k=1)
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)

    res = reporter.record_latencies("native_bm25_search", latencies)
    assert res.iterations == 1000
    assert res.mean_ms >= 0
    assert res.ops_per_sec > 0


def test_benchmark_harness_safety_matrix_eval_simulation() -> None:
    """Benchmark Safety Matrix risk classification over 5,000 iterations."""
    reporter = BenchmarkReporter()
    evaluator = get_safety_evaluator()

    latencies: list[float] = []
    actions = ["web_search", "email_send", "todoist_create_task", "unknown_action"]

    for i in range(5000):
        action = actions[i % len(actions)]
        t0 = time.perf_counter()
        evaluator.classify_risk(action)
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)

    res = reporter.record_latencies("native_safety_matrix_eval", latencies)
    assert res.iterations == 5000
    assert res.mean_ms >= 0
    assert res.ops_per_sec > 0


def test_benchmark_audit_journal_writer_throughput(tmp_path: Path) -> None:
    """Benchmark Audit Journal Writer append throughput over 2,000 iterations."""
    reporter = BenchmarkReporter()
    log_file = str(tmp_path / "benchmark_audit.jsonl")
    writer = get_journal_writer(log_file)

    latencies: list[float] = []
    sample_record = '{"timestamp": "2026-08-02T16:00:00", "step": "eval", "status": "APPROVED"}'

    for _ in range(2000):
        t0 = time.perf_counter()
        writer.append_record(sample_record)
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)

    res = reporter.record_latencies("native_audit_journal_append", latencies)
    assert res.iterations == 2000
    assert res.mean_ms >= 0
