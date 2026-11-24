"""Stateful Hypothesis state-machine fuzzing across ALOS concurrency & hysteresis engines.

Spec: specs/035-parallel-testing-and-qa-matrix/spec.md (FR-011)
ADR: ADR-0020
"""

from __future__ import annotations

import json
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule
from sqlalchemy import select

from alos.db.models import ComputeQueueJobModel
from alos.db.session import DatabaseManager
from alos.runtime import DaemonAlreadyRunningError, SingleInstanceLock, allocate_free_port
from alos.swarm.governor import (
    ContainerPauser,
    EvictionReport,
    GovernorState,
    HostGovernor,
    HysteresisConfig,
    ModelSpinner,
)
from alos.swarm.queue import QueueConfig, StickyEpochQueue
from alos.swarm.sensors import ScriptedSensor, SensorProvider

pytestmark = [pytest.mark.fuzz, pytest.mark.source]


class _FuzzSpinner(ModelSpinner):
    def __init__(self) -> None:
        super().__init__(port=allocate_free_port())
        self._tier: str | None = "fast_coder"

    @property
    def active_tier(self) -> str | None:
        return self._tier

    def evict_all(self, sensor: SensorProvider | None = None) -> EvictionReport:
        self._tier = None
        return EvictionReport(
            elapsed_s=0.01, graceful_unloaded=True, tree_killed=True, remaining_managed_vram_mb=0
        )


class StickyEpochQueueStateMachine(RuleBasedStateMachine):
    """Fuzz arbitrary sequences of enqueue, lease, preempt, complete, fail, and clock jumps."""

    def __init__(self) -> None:
        super().__init__()
        self._tmp = Path(tempfile.mkdtemp(prefix="alos_q_fuzz_"))
        self._now = datetime(2026, 11, 23, 8, 0, 0, tzinfo=timezone.utc)
        self._mono = 1000.0
        self.db = DatabaseManager(db_url=f"sqlite:///{(self._tmp / 'fuzz_q.db').as_posix()}")
        self.db.create_all_tables()
        self.cfg = QueueConfig(
            lease_ttl_s=60.0,
            max_epoch_s=300.0,
            max_open_merge_jobs=2,
            overflow_wait_s=600.0,
        )
        self.queue = StickyEpochQueue(
            db=self.db,
            config=self.cfg,
            now_fn=lambda: self._now,
            mono_fn=lambda: self._mono,
        )
        self._seq = 0
        self.enqueued_ids: set[str] = set()
        self.leased_ids: list[str] = []

    def teardown(self) -> None:
        self.db.engine.dispose()
        shutil.rmtree(self._tmp, ignore_errors=True)

    @rule(
        repo=st.sampled_from(["alos", "nectR"]),
        tier=st.sampled_from(["fast_coder", "reasoner"]),
        priority=st.integers(min_value=1, max_value=100),
        requires_merge=st.booleans(),
        allow_overflow=st.booleans(),
        max_attempts=st.integers(min_value=1, max_value=3),
    )
    def enqueue_job(
        self,
        repo: str,
        tier: str,
        priority: int,
        requires_merge: bool,
        allow_overflow: bool,
        max_attempts: int,
    ) -> None:
        self._seq += 1
        jid = f"fj-{self._seq:04d}"
        self.queue.enqueue(
            job_id=jid,
            repo_slug=repo,
            workflow_type="fuzz",
            model_tier=tier,
            priority=priority,
            requires_merge=requires_merge,
            allow_cloud_overflow=allow_overflow,
            max_attempts=max_attempts,
        )
        self.enqueued_ids.add(jid)

    @rule(active_tier=st.sampled_from([None, "fast_coder", "reasoner"]))
    def lease_job(self, active_tier: str | None) -> None:
        leased = self.queue.lease_next(worker_id="fuzz-w", active_tier=active_tier)
        if leased is not None and leased.job_id not in self.leased_ids:
            self.leased_ids.append(leased.job_id)

    @rule(ckpt=st.sampled_from(["node-a", "node-b", None]))
    def preempt_leased(self, ckpt: str | None) -> None:
        if not self.leased_ids:
            return
        jid = self.leased_ids.pop(0)
        self.queue.release_preempted(jid, checkpoint_ns=ckpt)

    @rule()
    def complete_leased(self) -> None:
        if not self.leased_ids:
            return
        jid = self.leased_ids.pop(0)
        self.queue.complete_job(jid, result_json={"ok": True})

    @rule()
    def fail_leased(self) -> None:
        if not self.leased_ids:
            return
        jid = self.leased_ids.pop(0)
        self.queue.fail_job(jid, error_msg="fuzzed error")

    @rule(delta_s=st.integers(min_value=5, max_value=400))
    def advance_clock(self, delta_s: int) -> None:
        self._now = self._now + timedelta(seconds=delta_s)
        self._mono += float(delta_s)
        # Re-synchronize tracked leased_ids if TTL expired
        if delta_s >= 60:
            self.leased_ids.clear()

    @invariant()
    def queue_invariants_hold(self) -> None:
        legal_states = {
            "queued",
            "leased",
            "preempted",
            "succeeded",
            "review_pending",
            "escalated",
            "overflow",
        }
        with self.db.get_session() as session:
            rows = list(session.scalars(select(ComputeQueueJobModel)))
        assert {r.job_id for r in rows} == self.enqueued_ids
        for repo in ("alos", "nectR"):
            active_merges = [
                r
                for r in rows
                if r.repo_slug == repo
                and r.requires_merge
                and r.state in ("review_pending", "leased")
            ]
            assert len(active_merges) <= self.cfg.max_open_merge_jobs
        for row in rows:
            assert row.state in legal_states
            assert row.attempts >= 0


class HostGovernorStateMachine(RuleBasedStateMachine):
    """Fuzz HostGovernor Schmitt-trigger hysteresis across thermal/gaming/idle transitions."""

    def __init__(self) -> None:
        super().__init__()
        self._t = 100.0
        self.sensor = ScriptedSensor()
        self.spinner = _FuzzSpinner()
        self.pauser = ContainerPauser(runner=lambda _cmd: 0)
        self.pauser.register("fuzz-container")
        self.cfg = HysteresisConfig()
        self.gov = HostGovernor(
            sensor=self.sensor,
            spinner=self.spinner,
            pauser=self.pauser,
            config=self.cfg,
            clock=lambda: self._t,
        )
        self.last_transition = self.gov.evaluate(has_queued_work=False)

    @rule(
        d3d=st.booleans(),
        gpu_c=st.floats(min_value=30.0, max_value=95.0, allow_nan=False, allow_infinity=False),
        vram_c=st.floats(min_value=40.0, max_value=105.0, allow_nan=False, allow_infinity=False),
        used_mb=st.integers(min_value=500, max_value=14000),
        idle_s=st.floats(min_value=0.0, max_value=900.0, allow_nan=False, allow_infinity=False),
        has_work=st.booleans(),
    )
    def step_telemetry_and_eval(
        self,
        d3d: bool,
        gpu_c: float,
        vram_c: float,
        used_mb: int,
        idle_s: float,
        has_work: bool,
    ) -> None:
        if has_work and self.gov.state == GovernorState.WARM_ACTIVE:
            self.spinner._tier = "fast_coder"
        self.sensor.update(
            d3d_fullscreen=d3d,
            gpu_temp_c=gpu_c,
            vram_temp_c=vram_c,
            used_vram_mb=used_mb,
            managed_vram_mb=0,
            user_idle_seconds=idle_s,
        )
        self.last_transition = self.gov.evaluate(has_queued_work=has_work)

    @rule(dt=st.floats(min_value=1.0, max_value=400.0, allow_nan=False, allow_infinity=False))
    def advance_time(self, dt: float) -> None:
        self._t += dt
        self.last_transition = self.gov.evaluate(has_queued_work=False)

    @invariant()
    def safety_and_preemption_invariants_hold(self) -> None:
        snap = self.last_transition.snapshot
        state = self.gov.state
        if snap.d3d_fullscreen:
            assert state == GovernorState.USER_PREEMPTED
            assert not self.last_transition.can_pull_work
        if state in (GovernorState.USER_PREEMPTED, GovernorState.COOLING_CUTOFF):
            assert self.gov.cancel_event.is_set()
            assert self.spinner.active_tier is None
            assert "fuzz-container" in self.pauser.paused_containers
        else:
            assert not self.gov.cancel_event.is_set()


class SingleInstanceLockStateMachine(RuleBasedStateMachine):
    """Fuzz SingleInstanceLock acquisition, release, and stale dead-PID reclamation."""

    def __init__(self) -> None:
        super().__init__()
        self._tmp = Path(tempfile.mkdtemp(prefix="alos_lk_fuzz_"))
        self.lock_path = self._tmp / "run" / "governor.lock"
        self.holder: SingleInstanceLock | None = None

    def teardown(self) -> None:
        if self.holder is not None:
            self.holder.release()
        shutil.rmtree(self._tmp, ignore_errors=True)

    @rule()
    def try_acquire(self) -> None:
        cand = SingleInstanceLock(self.lock_path)
        if self.holder is not None:
            with pytest.raises(DaemonAlreadyRunningError):
                cand.acquire()
        else:
            cand.acquire()
            self.holder = cand

    @rule()
    def release_holder(self) -> None:
        if self.holder is not None:
            self.holder.release()
            self.holder = None

    @rule()
    def write_stale_lock_when_free(self) -> None:
        if self.holder is None:
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)
            self.lock_path.write_text(json.dumps({"pid": 99_999_999}), encoding="utf-8")

    @invariant()
    def lock_exclusivity_invariant(self) -> None:
        if self.holder is not None:
            assert self.lock_path.exists()


TestStickyEpochQueueFuzz = StickyEpochQueueStateMachine.TestCase
TestStickyEpochQueueFuzz.settings = settings(max_examples=20, stateful_step_count=25, deadline=None)

TestHostGovernorFuzz = HostGovernorStateMachine.TestCase
TestHostGovernorFuzz.settings = settings(max_examples=20, stateful_step_count=25, deadline=None)

TestSingleInstanceLockFuzz = SingleInstanceLockStateMachine.TestCase
TestSingleInstanceLockFuzz.settings = settings(
    max_examples=20, stateful_step_count=20, deadline=None
)
