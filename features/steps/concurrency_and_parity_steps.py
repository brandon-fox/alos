"""Behave step definitions for concurrency_and_parity.feature (Spec 035)."""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from behave import given, then, when
from sqlalchemy import select

from alos.db.models import ComputeQueueJobModel
from alos.db.session import DatabaseManager
from alos.native.fallback import FallbackBM25Indexer, FallbackSafetyEvaluator
from alos.runtime import is_pid_alive
from alos.swarm.queue import StickyEpochQueue
from alos.swarm.sensors import query_win32_free_commit_mb


@given("a WAL-mode SQLite StickyEpochQueue with {count:d} queued jobs across 2 tiers")
def step_given_wal_queue(context: Any, count: int) -> None:
    db_path = context.tmp_dir / "bdd_contention.db"
    context.c_db = DatabaseManager(db_url=f"sqlite:///{db_path.as_posix()}")
    context.c_db.create_all_tables()
    context.c_queue = StickyEpochQueue(db=context.c_db)
    context.c_count = count
    for idx in range(count):
        tier = "fast_coder" if idx % 2 == 0 else "reasoner"
        context.c_queue.enqueue(f"bdd-j-{idx:02d}", "alos", "smoke", tier)


@when("{workers:d} concurrent threads lease and complete all runnable jobs")
def step_when_threads_drain(context: Any, workers: int) -> None:
    leased_ids: list[str] = []
    guard = threading.Lock()

    def _drain(wid: int) -> None:
        while True:
            job = context.c_queue.lease_next(worker_id=f"w-{wid}", active_tier="fast_coder")
            if job is None:
                return
            with guard:
                leased_ids.append(job.job_id)
            context.c_queue.complete_job(job.job_id, result_json={"w": wid})

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for fut in as_completed([pool.submit(_drain, i) for i in range(workers)]):
            fut.result()
    context.c_leased_ids = leased_ids


@then('every job transitions to "{expected}" with zero duplicate leases')
def step_then_zero_duplicates(context: Any, expected: str) -> None:
    assert len(context.c_leased_ids) == context.c_count
    assert len(set(context.c_leased_ids)) == context.c_count
    with context.c_db.get_session() as session:
        rows = list(session.scalars(select(ComputeQueueJobModel)))
    assert all(r.state == expected for r in rows)


@given('a FallbackBM25Indexer loaded with "{hdr1}" spec and "{hdr2}" vault chunks')
def step_given_bm25_chunks(context: Any, hdr1: str, hdr2: str) -> None:
    idx = FallbackBM25Indexer()
    idx.add_chunk(hdr1, "spec.md", "/spec.md", "spec", "risk tiers low medium high")
    idx.add_chunk(hdr2, "journal.md", "/journal.md", "vault", "morning reflection notes")
    context.bm25 = idx


@when('I search BM25 for "{query}" with top_k {top_k:d}')
def step_when_search_bm25(context: Any, query: str, top_k: int) -> None:
    context.bm25_hits = context.bm25.search(query, top_k=top_k)


@then('the top BM25 hit is "{expected_hdr}" with positive Okapi score')
def step_then_top_bm25_hit(context: Any, expected_hdr: str) -> None:
    assert len(context.bm25_hits) >= 1
    assert context.bm25_hits[0]["header"] == expected_hdr
    assert float(context.bm25_hits[0]["score"]) > 0.0


@then('classifying an unknown tool action returns fail-safe tier "{expected_tier}"')
def step_then_unknown_high(context: Any, expected_tier: str) -> None:
    assert FallbackSafetyEvaluator().classify_risk("unregistered_external_op") == expected_tier


@given("the current Windows host process PID")
def step_given_win_pid(context: Any) -> None:
    context.check_pid = os.getpid()


@then("is_pid_alive reports True for the current PID and positive free commit MiB")
def step_then_win_alive_and_commit(context: Any) -> None:
    assert is_pid_alive(context.check_pid) is True
    free_mb = query_win32_free_commit_mb()
    assert free_mb is not None and free_mb > 0


@given(
    "the current Linux host process PID and a synthetic meminfo file with {kb:d} kB MemAvailable"
)
def step_given_linux_pid_and_meminfo(context: Any, kb: int) -> None:
    context.check_pid = os.getpid()
    meminfo = context.tmp_dir / "meminfo"
    meminfo.write_text(f"MemTotal: 16777216 kB\nMemAvailable: {kb} kB\n", encoding="utf-8")
    context.meminfo_path = meminfo


@then("is_pid_alive reports True for the current PID and {expected_mb:d} MiB available memory")
def step_then_linux_alive_and_mem(context: Any, expected_mb: int) -> None:
    assert is_pid_alive(context.check_pid) is True
    assert query_win32_free_commit_mb(context.meminfo_path) == expected_mb
