"""Unit and integration tests for StickyEpochQueue and ComputeRuntimeLoop (Spec 032)."""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from alos.db.session import DatabaseManager
from alos.swarm.dispatcher import Ollama
from alos.swarm.governor import (
    GovernorState,
    HostGovernor,
    ModelSpinner,
)
from alos.swarm.queue import (
    ComputeRuntimeLoop,
    LeasedJob,
    PreemptedExecutionError,
    QueueConfig,
    StickyEpochQueue,
    main,
)
from alos.swarm.sensors import ScriptedSensor


class FakeWallClock:
    def __init__(self) -> None:
        self.dt = datetime(2026, 11, 23, 22, 0, 0, tzinfo=timezone.utc)
        self.mono = 500.0

    def now(self) -> datetime:
        return self.dt

    def monotonic(self) -> float:
        return self.mono

    def advance(self, seconds: float) -> None:
        self.dt += timedelta(seconds=seconds)
        self.mono += seconds


def _make_queue(
    tmp_path: Path, cfg: QueueConfig | None = None
) -> tuple[StickyEpochQueue, FakeWallClock]:
    clock = FakeWallClock()
    db = DatabaseManager(db_url=f"sqlite:///{tmp_path / 'queue.db'}")
    db.create_all_tables()
    q = StickyEpochQueue(db=db, config=cfg, now_fn=clock.now, mono_fn=clock.monotonic)
    return q, clock


def test_sticky_epoch_affinity_and_epoch_expiry_anti_starvation(tmp_path: Path) -> None:
    """Jobs matching active_tier drain together until max_epoch_s forces a fair rotation."""
    q, clock = _make_queue(tmp_path, QueueConfig(max_epoch_s=600.0, tier_affinity_bonus=40.0))
    q.enqueue("c1", "alos", "fix", "fast_coder", priority=65)
    q.enqueue("r1", "alos", "audit", "reasoner", priority=50)
    q.enqueue("r2", "alos", "audit", "reasoner", priority=50)

    # While reasoner is hot (< 600s epoch), r1 beats higher-base-priority c1 (50+40 > 65)
    first = q.lease_next(active_tier="reasoner")
    assert first is not None and first.job_id == "r1"
    q.complete_job("r1")

    # Advance past 600s epoch limit: affinity bonus drops so starving c1 (65 > 50) wins next epoch
    clock.advance(610.0)
    second = q.lease_next(active_tier="reasoner")
    assert second is not None and second.job_id == "c1"


def test_preempted_job_preserves_checkpoint_and_attempts(tmp_path: Path) -> None:
    """Preempting a leased job keeps attempts=1, stores checkpoint_ns, and resumes first."""
    q, _ = _make_queue(tmp_path)
    q.enqueue("job-a", "alos", "refactor", "fast_coder", priority=50)
    q.enqueue("job-b", "alos", "refactor", "fast_coder", priority=55)

    leased_b = q.lease_next(active_tier="fast_coder")
    assert leased_b is not None and leased_b.job_id == "job-b"
    assert leased_b.attempts == 1

    # Preempt job-b at LangGraph node checkpoint
    released = q.release_preempted("job-b", checkpoint_ns="lg-thread-42:node-3")
    assert released is not None
    assert released.state == "preempted"
    assert released.attempts == 1
    assert released.checkpoint_ns == "lg-thread-42:node-3"

    # Re-leasing resumes job-b without incrementing attempts to 2
    resumed = q.lease_next(active_tier="fast_coder")
    assert resumed is not None
    assert resumed.job_id == "job-b"
    assert resumed.attempts == 1
    assert resumed.checkpoint_ns == "lg-thread-42:node-3"


def test_merge_cap_skips_fourth_pr_while_running_no_merge_work(tmp_path: Path) -> None:
    """A repo with 3 review_pending merge jobs skips merge work while leasing no-merge work."""
    q, _ = _make_queue(tmp_path, QueueConfig(max_open_merge_jobs=3))
    for i in range(1, 4):
        q.enqueue(f"pr-{i}", "alos", "fix", "fast_coder", requires_merge=True)
        leased = q.lease_next(active_tier="fast_coder")
        assert leased is not None
        done = q.complete_job(leased.job_id)
        assert done.state == "review_pending"

    q.enqueue("pr-4-blocked", "alos", "fix", "fast_coder", priority=90, requires_merge=True)
    q.enqueue("index-ok", "alos", "index", "fast_coder", priority=40, requires_merge=False)

    next_job = q.lease_next(active_tier="fast_coder")
    assert next_job is not None
    assert next_job.job_id == "index-ok"


def test_overflow_promotion_lease_expiry_and_ledger(tmp_path: Path) -> None:
    """Expired leases reclaim, cloud-eligible jobs overflow, and ledger records deltas."""
    q, clock = _make_queue(tmp_path, QueueConfig(lease_ttl_s=60.0, overflow_wait_s=300.0))
    q.enqueue("stale-lease", "alos", "audit", "reasoner", priority=60)
    q.enqueue("cloud-ok", "alos", "research", "reasoner", priority=50, allow_cloud_overflow=True)

    leased = q.lease_next(active_tier="reasoner")
    assert leased is not None and leased.job_id == "stale-lease"

    # Advance 350s: stale-lease expires back to preempted; cloud-ok promotes to overflow
    clock.advance(350.0)
    reclaimed = q.lease_next(active_tier="reasoner")
    assert reclaimed is not None and reclaimed.job_id == "stale-lease"
    q.complete_job("stale-lease")

    sensor = ScriptedSensor()
    spinner = MagicMock(spec=ModelSpinner)
    spinner.active_tier = "reasoner"
    gov = HostGovernor(sensor=sensor, spinner=spinner)
    tr = gov.evaluate(has_queued_work=False)
    row = q.record_ledger_entry(tr, active_tier="reasoner")
    assert row["governor_state"] == GovernorState.WARM_LINGER.value
    assert row["jobs_waiting"] == 0


def test_runtime_loop_preemption_and_cli_commands(tmp_path: Path) -> None:
    """ComputeRuntimeLoop handles mid-flight PreemptedExecutionError and CLI subcommands."""
    q, _ = _make_queue(tmp_path)
    q.enqueue("j-mid", "alos", "code", "fast_coder")

    sensor = ScriptedSensor()
    spinner = MagicMock(spec=ModelSpinner)
    spinner.active_tier = None

    def activate_tier(tier: str) -> Ollama:
        spinner.active_tier = tier
        return Ollama()

    spinner.ensure_tier.side_effect = activate_tier
    gov = HostGovernor(sensor=sensor, spinner=spinner)
    loop = ComputeRuntimeLoop(governor=gov, queue=q)

    def preempting_executor(
        _job: LeasedJob, _client: Ollama, _cancel: threading.Event
    ) -> dict[str, Any]:
        raise PreemptedExecutionError("game started mid-step", checkpoint_ns="ckpt-step-2")

    res = loop.run_once(preempting_executor)
    assert res.outcome == "preempted"

    # Second run completes cleanly from checkpoint
    seen_ckpt: list[str | None] = []

    def succeeding_executor(
        job: LeasedJob, _client: Ollama, _cancel: threading.Event
    ) -> dict[str, Any]:
        seen_ckpt.append(job.checkpoint_ns)
        return {"ok": True}

    res2 = loop.run_once(succeeding_executor)
    assert res2.outcome == "completed"
    assert seen_ckpt == ["ckpt-step-2"]

    # Smoke CLI status, enqueue, mocked tick, and bounded daemon
    cli_db = f"sqlite:///{tmp_path / 'cli.db'}"
    assert main(["--db-url", cli_db, "--mock", "status"]) == 0
    assert (
        main(
            [
                "--db-url",
                cli_db,
                "--mock",
                "enqueue",
                "--id",
                "cli-1",
                "--tier",
                "fast_coder",
                "--prompt",
                "hello",
            ]
        )
        == 0
    )
    assert main(["--db-url", cli_db, "--mock", "tick"]) == 0
    daemon_db = f"sqlite:///{tmp_path / 'daemon.db'}"
    assert (
        main(["--db-url", daemon_db, "--mock", "daemon", "--max-ticks", "2", "--poll-s", "0.01"])
        == 0
    )


def test_retry_budget_escalation_and_throttled_tier_filter(tmp_path: Path) -> None:
    """Failing jobs retry up to max_attempts then escalate; THROTTLED skips cold tier swaps."""
    q, _ = _make_queue(tmp_path)
    q.enqueue("flaky", "alos", "fix", "fast_coder", max_attempts=2)

    first = q.lease_next(active_tier="fast_coder")
    assert first is not None and first.attempts == 1
    assert q.fail_job("flaky", "err-1").state == "queued"

    second = q.lease_next(active_tier="fast_coder")
    assert second is not None and second.attempts == 2
    assert q.fail_job("flaky", "err-2").state == "escalated"
    assert q.lease_next(active_tier="fast_coder") is None

    # THROTTLED allows warm tier ("reasoner") while holding back cold tier ("fast_coder")
    q.enqueue("cold-job", "alos", "fix", "fast_coder")
    sensor = ScriptedSensor()
    sensor.update(user_idle_seconds=5.0)
    spinner = MagicMock(spec=ModelSpinner)
    spinner.active_tier = "reasoner"
    gov = HostGovernor(sensor=sensor, spinner=spinner, state=GovernorState.WARM_ACTIVE)
    loop = ComputeRuntimeLoop(governor=gov, queue=q)
    tick = loop.run_once(lambda _j, _c, _e: {"ok": True})
    assert tick.outcome == "throttled_wait"
