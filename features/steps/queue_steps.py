"""Behave step definitions for sticky_epoch_queue.feature."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from behave import given, then, when

from alos.db.models import ComputeQueueJobModel
from alos.db.session import DatabaseManager
from alos.swarm.queue import QueueConfig, StickyEpochQueue


class _QueueTestClock:
    def __init__(self) -> None:
        self.dt = datetime(2026, 11, 23, 22, 0, 0, tzinfo=timezone.utc)
        self.mono = 200.0

    def now(self) -> datetime:
        return self.dt

    def monotonic(self) -> float:
        return self.mono

    def advance(self, seconds: float) -> None:
        self.dt += timedelta(seconds=seconds)
        self.mono += seconds


def _init_queue(context: Any, cfg: QueueConfig | None = None) -> None:
    clock = _QueueTestClock()
    db = DatabaseManager(db_url=f"sqlite:///{context.tmp_dir / 'epoch_queue.db'}")
    db.create_all_tables()
    context.q_clock = clock
    context.q_db = db
    context.queue = StickyEpochQueue(db=db, config=cfg, now_fn=clock.now, mono_fn=clock.monotonic)


@given("an isolated SQLite sticky epoch queue")
def step_given_default_queue(context: Any) -> None:
    _init_queue(context)


@given("an isolated SQLite sticky epoch queue with {max_epoch_s:d}s max epoch")
def step_given_epoch_cap_queue(context: Any, max_epoch_s: int) -> None:
    _init_queue(context, QueueConfig(max_epoch_s=float(max_epoch_s), tier_affinity_bonus=40.0))


@given("an isolated SQLite sticky epoch queue with max {max_merge:d} open merge jobs")
def step_given_merge_cap_queue(context: Any, max_merge: int) -> None:
    _init_queue(context, QueueConfig(max_open_merge_jobs=max_merge))


@given(
    "an isolated SQLite sticky epoch queue with {ttl_s:d}s lease TTL "
    "and {overflow_s:d}s overflow wait"
)
def step_given_ttl_overflow_queue(context: Any, ttl_s: int, overflow_s: int) -> None:
    _init_queue(context, QueueConfig(lease_ttl_s=float(ttl_s), overflow_wait_s=float(overflow_s)))


@given("jobs enqueued in order: {specs_csv}")
def step_given_enqueued_specs(context: Any, specs_csv: str) -> None:
    for raw in specs_csv.split(","):
        token = raw.strip().strip('"')
        job_id, tier, prio_str = token.split(":")
        context.queue.enqueue(job_id, "alos", "task", tier, priority=int(prio_str))
        context.q_clock.advance(1.0)


@when('a worker leases and completes all 4 jobs starting with active tier "{start_tier}"')
def step_when_lease_all_four(context: Any, start_tier: str) -> None:
    leased_ids: list[str] = []
    active: str | None = start_tier
    for _ in range(4):
        job = context.queue.lease_next(active_tier=active)
        assert job is not None
        leased_ids.append(job.job_id)
        active = job.model_tier
        context.queue.complete_job(job.job_id)
    context.leased_ids = leased_ids


@then('the leased job order is "{expected_csv}"')
def step_then_leased_order(context: Any, expected_csv: str) -> None:
    assert ",".join(context.leased_ids) == expected_csv


@when('a worker leases one job with active tier "{tier}"')
@when('a worker leases the next job with active tier "{tier}"')
def step_when_lease_one(context: Any, tier: str) -> None:
    job = context.queue.lease_next(active_tier=tier)
    assert job is not None
    context.last_leased = job


@then('the leased job is "{expected_id}"')
def step_then_leased_id(context: Any, expected_id: str) -> None:
    assert context.last_leased.job_id == expected_id
    context.queue.complete_job(expected_id)


@when("the monotonic clock advances {sec:d}s past the epoch cap")
def step_when_advance_mono(context: Any, sec: int) -> None:
    context.q_clock.advance(float(sec))


@when('a worker leases the top job and preempts it at checkpoint "{ckpt}"')
def step_when_lease_and_preempt(context: Any, ckpt: str) -> None:
    job = context.queue.lease_next(active_tier="fast_coder")
    assert job is not None
    context.preempted_job = context.queue.release_preempted(job.job_id, checkpoint_ns=ckpt)


@then(
    'job "{job_id}" is stored in state "{state}" with {attempts:d} attempt and checkpoint "{ckpt}"'
)
def step_then_stored_preempted(
    context: Any, job_id: str, state: str, attempts: int, ckpt: str
) -> None:
    with context.q_db.get_session() as session:
        row = session.get(ComputeQueueJobModel, job_id)
        assert row is not None
        assert row.state == state
        assert row.attempts == attempts
        assert row.checkpoint_ns == ckpt


@then('the resumed job is "{job_id}" with {attempts:d} attempt and checkpoint "{ckpt}"')
def step_then_leased_preempted_details(context: Any, job_id: str, attempts: int, ckpt: str) -> None:
    job = context.last_leased
    assert job.job_id == job_id
    assert job.attempts == attempts
    assert job.checkpoint_ns == ckpt


@given('a job "{job_id}" on tier "{tier}" with max_attempts {max_att:d}')
def step_given_retry_job(context: Any, job_id: str, tier: str, max_att: int) -> None:
    context.queue.enqueue(job_id, "alos", "check", tier, max_attempts=max_att)


@when('"{job_id}" is leased and fails with "{err}"')
@when('"{job_id}" is leased again and fails with "{err}"')
def step_when_lease_and_fail(context: Any, job_id: str, err: str) -> None:
    leased = context.queue.lease_next(active_tier="fast_coder")
    assert leased is not None and leased.job_id == job_id
    context.failed_job = context.queue.fail_job(job_id, err)


@then('job "{job_id}" returns to state "{expected_state}" with {att:d} attempt')
@then('job "{job_id}" moves to state "{expected_state}" with {att:d} attempts')
def step_then_failed_state(context: Any, job_id: str, expected_state: str, att: int) -> None:
    with context.q_db.get_session() as session:
        row = session.get(ComputeQueueJobModel, job_id)
        assert row is not None
        assert row.state == expected_state
        assert row.attempts == att


@given('{count:d} completed merge jobs are pending review on repository "{repo}"')
def step_given_pending_prs(context: Any, count: int, repo: str) -> None:
    for idx in range(1, count + 1):
        jid = f"existing-pr-{idx}"
        context.queue.enqueue(jid, repo, "pr", "fast_coder", requires_merge=True)
        leased = context.queue.lease_next(active_tier="fast_coder")
        assert leased is not None
        context.queue.complete_job(leased.job_id)


@when(
    'merge job "{pr_id}" and no-merge job "{idx_id}" on "{repo1}" '
    'and merge job "{other_id}" on "{repo2}" are enqueued'
)
def step_when_mixed_merge_enqueued(
    context: Any, pr_id: str, idx_id: str, repo1: str, other_id: str, repo2: str
) -> None:
    context.queue.enqueue(pr_id, repo1, "pr", "fast_coder", priority=95, requires_merge=True)
    context.queue.enqueue(idx_id, repo1, "index", "fast_coder", priority=50, requires_merge=False)
    context.queue.enqueue(other_id, repo2, "pr", "fast_coder", priority=45, requires_merge=True)


@then('leasing two jobs yields "{first_id}" and "{second_id}" while leaving "{blocked_id}" queued')
def step_then_merge_cap_enforced(
    context: Any, first_id: str, second_id: str, blocked_id: str
) -> None:
    j1 = context.queue.lease_next(active_tier="fast_coder")
    j2 = context.queue.lease_next(active_tier="fast_coder")
    j3 = context.queue.lease_next(active_tier="fast_coder")
    assert j1 is not None and j1.job_id == first_id
    assert j2 is not None and j2.job_id == second_id
    assert j3 is None
    with context.q_db.get_session() as session:
        blocked = session.get(ComputeQueueJobModel, blocked_id)
        assert blocked is not None and blocked.state == "queued"


@given('job "{j1}" with priority {p1:d} and cloud-overflow job "{j2}" with priority {p2:d}')
def step_given_lease_and_overflow_jobs(context: Any, j1: str, p1: int, j2: str, p2: int) -> None:
    context.queue.enqueue(j1, "alos", "audit", "reasoner", priority=p1)
    context.queue.enqueue(
        j2, "alos", "research", "reasoner", priority=p2, allow_cloud_overflow=True
    )


@when('"{job_id}" is leased and wall clock advances {sec:d}s without completion')
def step_when_lease_expires(context: Any, job_id: str, sec: int) -> None:
    leased = context.queue.lease_next(active_tier="reasoner")
    assert leased is not None and leased.job_id == job_id
    context.q_clock.advance(float(sec))


@when("a worker leases the next available job")
def step_when_lease_next_avail(context: Any) -> None:
    context.reclaimed_job = context.queue.lease_next(active_tier="reasoner")


@then('"{reclaimed_id}" is reclaimed and re-leased while "{overflow_id}" moves to state "overflow"')
def step_then_reclaimed_and_overflowed(context: Any, reclaimed_id: str, overflow_id: str) -> None:
    assert context.reclaimed_job is not None
    assert context.reclaimed_job.job_id == reclaimed_id
    with context.q_db.get_session() as session:
        ov = session.get(ComputeQueueJobModel, overflow_id)
        assert ov is not None and ov.state == "overflow"
