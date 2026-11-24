"""Sticky Model-Epoch Work Queue, Capacity Ledger, and Preemptible Runtime Loop.

Spec: specs/032-preemptible-compute-governor/spec.md (FR-006, FR-007, FR-008, FR-009)
ADR: docs/adr/0014-adopt-preemptible-host-governor-and-sticky-model-epoch-queue.md
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import signal
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alos.db.models import ComputeCapacityLedgerModel, ComputeQueueJobModel
from alos.db.session import DatabaseManager
from alos.runtime import (
    DaemonAlreadyRunningError,
    HealthHeartbeat,
    RuntimePaths,
    SingleInstanceLock,
    bootstrap_home,
    query_jobs,
    query_ledger,
    run_doctor,
)
from alos.swarm.dispatcher import Ollama
from alos.swarm.governor import (
    EvictionReport,
    GovernorState,
    GovernorTransition,
    HostGovernor,
    ModelSpinner,
    is_embedding_model,
    is_thermal_throttled,
)
from alos.swarm.sensors import (
    ScriptedSensor,
    SensorProvider,
    TelemetrySnapshot,
    WindowsNativeSensor,
)

RUNNABLE_STATES = ("queued", "preempted")


class PreemptedExecutionError(Exception):
    """Raised by an executor when ``cancel_event`` fires mid-node, carrying checkpoint state."""

    def __init__(self, message: str = "execution preempted", checkpoint_ns: str | None = None):
        super().__init__(message)
        self.checkpoint_ns = checkpoint_ns


@dataclass(frozen=True)
class QueueConfig:
    """Policy knobs for sticky model-epoch batching, lease TTL, PR caps, and cloud overflow."""

    lease_ttl_s: float = 300.0
    max_epoch_s: float = 1200.0
    tier_affinity_bonus: float = 40.0
    preempted_resume_bonus: float = 20.0
    age_weight_per_min: float = 0.5
    max_open_merge_jobs: int = 3
    overflow_wait_s: float = 7200.0


@dataclass(frozen=True)
class LeasedJob:
    """Detached value object representing a job leased by a worker."""

    job_id: str
    repo_slug: str
    workflow_type: str
    model_tier: str
    priority: int
    requires_merge: bool
    allow_cloud_overflow: bool
    payload: dict[str, Any]
    checkpoint_ns: str | None
    state: str
    attempts: int
    max_attempts: int


@dataclass(frozen=True)
class LoopTickResult:
    """Outcome of a single ``ComputeRuntimeLoop.run_once()`` cycle."""

    outcome: str
    transition: GovernorTransition
    job_id: str | None = None
    active_tier: str | None = None


def _as_utc(dt: datetime) -> datetime:
    """Normalize SQLite naive timestamps and PostgreSQL aware timestamps to UTC."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _to_leased_job(row: ComputeQueueJobModel) -> LeasedJob:
    return LeasedJob(
        job_id=row.job_id,
        repo_slug=row.repo_slug,
        workflow_type=row.workflow_type,
        model_tier=row.model_tier,
        priority=row.priority,
        requires_merge=row.requires_merge,
        allow_cloud_overflow=row.allow_cloud_overflow,
        payload=dict(row.payload or {}),
        checkpoint_ns=row.checkpoint_ns,
        state=row.state,
        attempts=row.attempts,
        max_attempts=row.max_attempts,
    )


class StickyEpochQueue:
    """Pull-based ACID work queue that groups leases by active ``model_tier`` epoch."""

    def __init__(
        self,
        db: DatabaseManager,
        config: QueueConfig | None = None,
        now_fn: Callable[[], datetime] | None = None,
        mono_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self.db = db
        self.config = config or QueueConfig()
        self._now = now_fn or (lambda: datetime.now(timezone.utc))
        self._mono = mono_fn
        self._epoch_tier: str | None = None
        self._epoch_started_at: float | None = None
        self._done_delta = 0
        self._preempted_delta = 0
        self._overflow_delta = 0

    def enqueue(
        self,
        job_id: str,
        repo_slug: str,
        workflow_type: str,
        model_tier: str,
        payload: dict[str, Any] | None = None,
        priority: int = 50,
        requires_merge: bool = False,
        allow_cloud_overflow: bool = False,
        checkpoint_ns: str | None = None,
        max_attempts: int = 2,
    ) -> LeasedJob:
        """Insert a new job into ``compute_work_queue``."""
        now = self._now()
        with self.db.get_session() as session:
            row = ComputeQueueJobModel(
                job_id=job_id,
                repo_slug=repo_slug,
                workflow_type=workflow_type,
                model_tier=model_tier,
                priority=priority,
                requires_merge=requires_merge,
                allow_cloud_overflow=allow_cloud_overflow,
                payload=payload or {},
                checkpoint_ns=checkpoint_ns,
                state="queued",
                attempts=0,
                max_attempts=max_attempts,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            session.flush()
            return _to_leased_job(row)

    def _reclaim_expired_leases(self, session: Session, now: datetime) -> None:
        reclaimed = False
        stmt = select(ComputeQueueJobModel).where(ComputeQueueJobModel.state == "leased")
        for row in session.scalars(stmt):
            if row.leased_until is not None and _as_utc(row.leased_until) <= now:
                row.state = "preempted"
                row.leased_by = None
                row.leased_until = None
                row.updated_at = now
                reclaimed = True
        if reclaimed:
            session.flush()

    def _promote_overflow_jobs(self, session: Session, now: datetime) -> int:
        promoted = 0
        stmt = select(ComputeQueueJobModel).where(
            ComputeQueueJobModel.state.in_(RUNNABLE_STATES),
            ComputeQueueJobModel.allow_cloud_overflow.is_(True),
        )
        for row in session.scalars(stmt):
            waited_s = (now - _as_utc(row.created_at)).total_seconds()
            if waited_s >= self.config.overflow_wait_s:
                row.state = "overflow"
                row.updated_at = now
                promoted += 1
        if promoted:
            session.flush()
        self._overflow_delta += promoted
        return promoted

    def _saturated_merge_repos(self, session: Session) -> set[str]:
        stmt = (
            select(ComputeQueueJobModel.repo_slug, func.count(ComputeQueueJobModel.job_id))
            .where(ComputeQueueJobModel.state == "review_pending")
            .group_by(ComputeQueueJobModel.repo_slug)
        )
        return {
            str(repo)
            for repo, count in session.execute(stmt).all()
            if int(count) >= self.config.max_open_merge_jobs
        }

    def _is_epoch_fresh(self, active_tier: str | None) -> bool:
        if active_tier is None:
            return False
        now_m = self._mono()
        if self._epoch_tier != active_tier or self._epoch_started_at is None:
            self._epoch_tier = active_tier
            self._epoch_started_at = now_m
            return True
        return (now_m - self._epoch_started_at) < self.config.max_epoch_s

    def _score_row(
        self,
        row: ComputeQueueJobModel,
        active_tier: str | None,
        epoch_fresh: bool,
        now: datetime,
    ) -> float:
        wait_min = max(0.0, (now - _as_utc(row.created_at)).total_seconds() / 60.0)
        score = float(row.priority) + (wait_min * self.config.age_weight_per_min)
        if epoch_fresh and active_tier and row.model_tier == active_tier:
            score += self.config.tier_affinity_bonus
        if row.state == "preempted":
            score += self.config.preempted_resume_bonus
        return score

    def _update_epoch_tracker(self, chosen_tier: str) -> None:
        if self._epoch_tier != chosen_tier:
            self._epoch_tier = chosen_tier
            self._epoch_started_at = self._mono()

    def has_runnable_work(self) -> bool:
        """Return True when at least one runnable job is waiting and not merge-blocked."""
        now = self._now()
        with self.db.get_session() as session:
            self._reclaim_expired_leases(session, now)
            capped = self._saturated_merge_repos(session)
            stmt = select(ComputeQueueJobModel).where(
                ComputeQueueJobModel.state.in_(RUNNABLE_STATES)
            )
            for row in session.scalars(stmt):
                if not (row.requires_merge and row.repo_slug in capped):
                    return True
        return False

    def lease_next(
        self,
        worker_id: str = "local-worker-1",
        active_tier: str | None = None,
        allowed_tier_only: str | None = None,
    ) -> LeasedJob | None:
        """Atomically lease the highest-scoring runnable job using ``SKIP LOCKED`` semantics."""
        now = self._now()
        epoch_fresh = self._is_epoch_fresh(active_tier)
        with self.db.get_session() as session:
            self._reclaim_expired_leases(session, now)
            self._promote_overflow_jobs(session, now)
            capped = self._saturated_merge_repos(session)
            stmt = (
                select(ComputeQueueJobModel)
                .where(ComputeQueueJobModel.state.in_(RUNNABLE_STATES))
                .with_for_update(skip_locked=True)
            )
            candidates = [
                r
                for r in session.scalars(stmt)
                if not (r.requires_merge and r.repo_slug in capped)
                and (allowed_tier_only is None or r.model_tier == allowed_tier_only)
            ]
            if not candidates:
                return None
            candidates.sort(
                key=lambda r: (
                    -self._score_row(r, active_tier, epoch_fresh, now),
                    _as_utc(r.created_at),
                    r.job_id,
                )
            )
            winner = candidates[0]
            if winner.state == "queued":
                winner.attempts += 1
            winner.state = "leased"
            winner.leased_by = worker_id
            winner.leased_until = now + timedelta(seconds=self.config.lease_ttl_s)
            winner.updated_at = now
            self._update_epoch_tracker(winner.model_tier)
            session.flush()
            return _to_leased_job(winner)

    def release_preempted(self, job_id: str, checkpoint_ns: str | None = None) -> LeasedJob | None:
        """Return an interrupted job to ``preempted`` without burning failure retry attempts."""
        now = self._now()
        with self.db.get_session() as session:
            row = session.get(ComputeQueueJobModel, job_id)
            if row is None:
                return None
            row.state = "preempted"
            if checkpoint_ns is not None:
                row.checkpoint_ns = checkpoint_ns
            row.leased_by = None
            row.leased_until = None
            row.updated_at = now
            self._preempted_delta += 1
            session.flush()
            return _to_leased_job(row)

    def complete_job(self, job_id: str, result_json: dict[str, Any] | None = None) -> LeasedJob:
        """Mark a leased job ``review_pending`` (if merge work) or ``succeeded``."""
        now = self._now()
        with self.db.get_session() as session:
            row = session.get(ComputeQueueJobModel, job_id)
            if row is None:
                raise KeyError(f"unknown job_id {job_id!r}")
            row.state = "review_pending" if row.requires_merge else "succeeded"
            row.result_json = result_json or {}
            row.leased_by = None
            row.leased_until = None
            row.updated_at = now
            self._done_delta += 1
            session.flush()
            return _to_leased_job(row)

    def fail_job(self, job_id: str, error_msg: str) -> LeasedJob:
        """Re-queue failed job if under ``max_attempts``, else mark ``escalated``."""
        now = self._now()
        with self.db.get_session() as session:
            row = session.get(ComputeQueueJobModel, job_id)
            if row is None:
                raise KeyError(f"unknown job_id {job_id!r}")
            row.last_error = error_msg
            row.leased_by = None
            row.leased_until = None
            row.state = "queued" if row.attempts < row.max_attempts else "escalated"
            row.updated_at = now
            session.flush()
            return _to_leased_job(row)

    def record_ledger_entry(
        self, transition: GovernorTransition, active_tier: str | None
    ) -> dict[str, Any]:
        """Persist a capacity & thermal telemetry row and reset delta counters."""
        now = self._now()
        with self.db.get_session() as session:
            waiting_rows = list(
                session.scalars(
                    select(ComputeQueueJobModel).where(
                        ComputeQueueJobModel.state.in_(RUNNABLE_STATES)
                    )
                )
            )
            oldest_wait = max(
                ((now - _as_utc(r.created_at)).total_seconds() for r in waiting_rows),
                default=0.0,
            )
            entry = ComputeCapacityLedgerModel(
                recorded_at=now,
                governor_state=transition.state.value,
                active_tier=active_tier,
                gpu_temp_c=transition.snapshot.gpu_temp_c,
                vram_temp_c=transition.snapshot.vram_temp_c,
                gpu_util_pct=transition.snapshot.gpu_util_pct,
                used_vram_mb=transition.snapshot.used_vram_mb,
                managed_vram_mb=transition.snapshot.managed_vram_mb,
                jobs_waiting=len(waiting_rows),
                jobs_done_delta=self._done_delta,
                jobs_preempted_delta=self._preempted_delta,
                jobs_overflow_delta=self._overflow_delta,
                oldest_wait_seconds=round(max(0.0, oldest_wait), 1),
            )
            session.add(entry)
            self._done_delta = self._preempted_delta = self._overflow_delta = 0
            session.flush()
            return {
                "governor_state": entry.governor_state,
                "active_tier": entry.active_tier,
                "jobs_waiting": entry.jobs_waiting,
                "oldest_wait_seconds": entry.oldest_wait_seconds,
                "gpu_temp_c": entry.gpu_temp_c,
                "managed_vram_mb": entry.managed_vram_mb,
            }


JobExecutor = Callable[[LeasedJob, Ollama, threading.Event], dict[str, Any]]


@dataclass
class ComputeRuntimeLoop:
    """Connects ``HostGovernor``, ``ModelSpinner``, and ``StickyEpochQueue`` into a start loop."""

    governor: HostGovernor
    queue: StickyEpochQueue
    worker_id: str = "alos-local-1"
    throttled_swap_hold_s: float = 5.0
    _last_linger_refresh: float = field(default=0.0, init=False, repr=False)
    _throttled_wait_since: float | None = field(default=None, init=False, repr=False)

    def _maybe_refresh_linger(self, state: GovernorState) -> None:
        if state != GovernorState.WARM_LINGER:
            return
        now = time.monotonic()
        if (now - self._last_linger_refresh) >= 120.0:
            self.governor.spinner.refresh_keep_alive()
            self._last_linger_refresh = now

    def _resolve_tier_filter(self, transition: GovernorTransition) -> str | None:
        if transition.state != GovernorState.THROTTLED:
            self._throttled_wait_since = None
            return None
        if is_thermal_throttled(transition.snapshot, self.governor.config):
            return self.governor.spinner.active_tier
        if (
            self._throttled_wait_since is not None
            and (time.monotonic() - self._throttled_wait_since) >= self.throttled_swap_hold_s
        ):
            return None
        return self.governor.spinner.active_tier

    def _execute_leased_job(
        self, job: LeasedJob, executor: JobExecutor, pre_transition: GovernorTransition
    ) -> tuple[str, GovernorTransition]:
        try:
            client = self.governor.spinner.ensure_tier(job.model_tier)
            result = executor(job, client, self.governor.cancel_event)
        except PreemptedExecutionError as exc:
            self.queue.release_preempted(job.job_id, checkpoint_ns=exc.checkpoint_ns)
            return "preempted", self.governor.evaluate(has_queued_work=True)
        except Exception as exc:
            self.queue.fail_job(job.job_id, str(exc))
            return "failed", pre_transition
        post = self.governor.evaluate(has_queued_work=True)
        if not post.can_pull_work or self.governor.cancel_event.is_set():
            ckpt = str(result["checkpoint_ns"]) if "checkpoint_ns" in result else job.checkpoint_ns
            self.queue.release_preempted(job.job_id, checkpoint_ns=ckpt)
            return "preempted", post
        self.queue.complete_job(job.job_id, result_json=result)
        return "completed", post

    def run_once(self, executor: JobExecutor) -> LoopTickResult:
        """Run a single non-blocking poll-and-execute step."""
        has_work = self.queue.has_runnable_work()
        transition = self.governor.evaluate(has_queued_work=has_work)
        if not transition.can_pull_work:
            return LoopTickResult(
                outcome="gated",
                transition=transition,
                active_tier=self.governor.spinner.active_tier,
            )
        tier_filter = self._resolve_tier_filter(transition)
        job = self.queue.lease_next(
            worker_id=self.worker_id,
            active_tier=self.governor.spinner.active_tier,
            allowed_tier_only=tier_filter,
        )
        if job is None:
            if transition.state == GovernorState.THROTTLED and self._throttled_wait_since is None:
                self._throttled_wait_since = time.monotonic()
            self._maybe_refresh_linger(transition.state)
            outcome = "throttled_wait" if transition.state == GovernorState.THROTTLED else "starved"
            return LoopTickResult(
                outcome=outcome,
                transition=transition,
                active_tier=self.governor.spinner.active_tier,
            )
        self._throttled_wait_since = None
        outcome, final_transition = self._execute_leased_job(job, executor, transition)
        return LoopTickResult(
            outcome=outcome,
            transition=final_transition,
            job_id=job.job_id,
            active_tier=self.governor.spinner.active_tier,
        )


def _execute_embed_prompt(
    job: LeasedJob, client: Ollama, model: str, cancel_event: threading.Event
) -> dict[str, Any]:
    resp = client.call(
        "/api/embed",
        {
            "model": model,
            "input": str(job.payload.get("prompt", "")),
            "keep_alive": "10m",
        },
        timeout=float(job.payload.get("timeout_s", 60.0)),
    )
    if cancel_event.is_set():
        raise PreemptedExecutionError("cancelled during embedding", job.checkpoint_ns)
    embeddings = resp.get("embeddings") or []
    dim = len(embeddings[0]) if embeddings and isinstance(embeddings[0], list) else 0
    return {
        "response": f"embedded:{model}:dim={dim}",
        "model": model,
        "embedding_dim": dim,
        "eval_count": resp.get("prompt_eval_count"),
        "done_reason": "stop",
    }


def default_prompt_executor(
    job: LeasedJob, client: Ollama, cancel_event: threading.Event
) -> dict[str, Any]:
    """Minimal built-in executor running a structured prompt or embedding on the warm tier."""
    if cancel_event.is_set():
        raise PreemptedExecutionError("cancelled before generation", job.checkpoint_ns)
    shown = client.call("/api/ps", timeout=5.0).get("models", [])
    active_entry = shown[0] if shown else {}
    fallback_default = (
        "nomic-embed-text:latest" if job.model_tier == "embed" else "qwen2.5-coder:7b-instruct"
    )
    model = str(job.payload.get("model") or active_entry.get("name") or fallback_default)
    if is_embedding_model(model, job.model_tier):
        return _execute_embed_prompt(job, client, model, cancel_event)
    opts: dict[str, Any] = {"num_predict": int(job.payload.get("max_tokens", 512))}
    ctx_len = int(active_entry.get("context_length", 0) or 0)
    if ctx_len > 0:
        opts["num_ctx"] = ctx_len
    resp = client.call(
        "/api/generate",
        {
            "model": model,
            "prompt": str(job.payload.get("prompt", "Summarize status.")),
            "stream": False,
            "keep_alive": "10m",
            "options": opts,
        },
        timeout=float(job.payload.get("timeout_s", 60.0)),
    )
    if cancel_event.is_set():
        raise PreemptedExecutionError("cancelled during generation", job.checkpoint_ns)
    return {
        "response": str(resp.get("response", "")).strip(),
        "model": model,
        "eval_count": resp.get("eval_count"),
        "done_reason": resp.get("done_reason"),
    }


class _InMemoryMockSpinner(ModelSpinner):
    """Deterministic in-memory spinner used when ``ALOS_SWARM_MODE=mock`` or ``--mock`` is set."""

    def __init__(self) -> None:
        super().__init__(port=11497)
        self._mock_tier: str | None = None

    @property
    def active_tier(self) -> str | None:
        return self._mock_tier

    def ensure_tier(self, tier_name: str, warm_load: bool = True) -> Ollama:
        if tier_name not in self.tiers:
            raise KeyError(f"unknown model tier {tier_name!r}")
        self._mock_tier = tier_name
        return Ollama(self.host)

    def refresh_keep_alive(self) -> bool:
        return self._mock_tier is not None

    def evict_all(self, sensor: SensorProvider | None = None) -> EvictionReport:
        self._mock_tier = None
        return EvictionReport(
            elapsed_s=0.01, graceful_unloaded=True, tree_killed=False, remaining_managed_vram_mb=0
        )


def mock_prompt_executor(
    job: LeasedJob, _client: Ollama, cancel_event: threading.Event
) -> dict[str, Any]:
    """Deterministic mock prompt executor for offline CLI and BDD contract verification."""
    if cancel_event.is_set():
        raise PreemptedExecutionError("mock cancelled", job.checkpoint_ns)
    prompt_text = str(job.payload.get("prompt", ""))
    return {"response": f"MOCK_OK:{job.model_tier}:{prompt_text[:32]}", "eval_count": 8}


def _default_db_url(home: Path | str | None = None) -> str:
    return RuntimePaths.resolve(home).resolve_db_url()


def _build_sensor_from_env(mock_mode: bool, spinner: ModelSpinner) -> SensorProvider:
    if not mock_mode:
        return WindowsNativeSensor(managed_pids_fn=spinner.managed_pids)
    raw = os.environ.get("ALOS_MOCK_SENSOR_JSON", "").strip()
    overrides: dict[str, Any] = json.loads(raw) if raw else {}
    snap = TelemetrySnapshot(
        gpu_temp_c=float(overrides.get("gpu_temp_c", 42.0)),
        vram_temp_c=overrides.get("vram_temp_c"),
        cpu_temp_c=overrides.get("cpu_temp_c"),
        gpu_util_pct=int(overrides.get("gpu_util_pct", 5)),
        total_vram_mb=int(overrides.get("total_vram_mb", 16303)),
        used_vram_mb=int(overrides.get("used_vram_mb", 2400)),
        managed_vram_mb=int(overrides.get("managed_vram_mb", 0)),
        d3d_fullscreen=bool(overrides.get("d3d_fullscreen", False)),
        user_idle_seconds=float(overrides.get("user_idle_seconds", 600.0)),
        blocked_process=overrides.get("blocked_process"),
    )
    return ScriptedSensor(snap)


def _build_default_stack(db_url: str, mock_mode: bool = False) -> ComputeRuntimeLoop:
    db = DatabaseManager(db_url=db_url)
    db.create_all_tables()
    spinner: ModelSpinner = _InMemoryMockSpinner() if mock_mode else ModelSpinner()
    sensor = _build_sensor_from_env(mock_mode, spinner)
    governor = HostGovernor(sensor=sensor, spinner=spinner)
    queue = StickyEpochQueue(db=db)
    return ComputeRuntimeLoop(governor=governor, queue=queue)


def _emit_daemon_event(payload: dict[str, Any]) -> None:
    print(json.dumps(payload), flush=True)


@contextlib.contextmanager
def _managed_stop_signals(stop_event: threading.Event) -> Any:
    """Register SIGTERM/SIGINT/SIGBREAK handlers on the main thread and restore on exit."""
    if threading.current_thread() is not threading.main_thread():
        yield
        return

    def _on_signal(_signum: int, _frame: Any) -> None:
        stop_event.set()

    tracked = [signal.SIGINT, signal.SIGTERM]
    sigbreak = getattr(signal, "SIGBREAK", None)
    if sigbreak is not None:
        tracked.append(sigbreak)
    previous = {sig: signal.getsignal(sig) for sig in tracked}
    for sig in tracked:
        signal.signal(sig, _on_signal)
    try:
        yield
    finally:
        for sig, prev_handler in previous.items():
            signal.signal(sig, prev_handler)


def _daemon_step(
    loop: ComputeRuntimeLoop,
    executor: JobExecutor,
    heartbeat: HealthHeartbeat,
    ticks: int,
    last_state: GovernorState | None,
    last_ledger: float,
    ledger_interval_s: float,
) -> tuple[GovernorState, float]:
    tick = loop.run_once(executor)
    cur_state = tick.transition.state
    heartbeat.write("running", cur_state.value, tick.active_tier)
    if tick.job_id is not None or cur_state != last_state:
        _emit_daemon_event(
            {
                "event": "daemon_tick",
                "tick": ticks,
                "outcome": tick.outcome,
                "state": cur_state.value,
                "job_id": tick.job_id,
                "active_tier": tick.active_tier,
            }
        )
    now = time.monotonic()
    if (now - last_ledger) >= ledger_interval_s or tick.outcome in ("completed", "preempted"):
        loop.queue.record_ledger_entry(tick.transition, loop.governor.spinner.active_tier)
        last_ledger = now
    return cur_state, last_ledger


def _run_daemon(
    loop: ComputeRuntimeLoop,
    executor: JobExecutor,
    paths: RuntimePaths,
    poll_s: float,
    ledger_interval_s: float,
    max_ticks: int | None,
    stop_event: threading.Event | None = None,
) -> int:
    """Run the standing governor + queue pull loop with PID locking and SIGTERM safety."""
    stopper = stop_event or threading.Event()
    heartbeat = HealthHeartbeat(paths.health_file)
    try:
        lock = SingleInstanceLock(paths.lock_file)
        lock.acquire()
    except DaemonAlreadyRunningError as exc:
        _emit_daemon_event({"event": "daemon_locked", "error": str(exc)})
        return 3

    ticks = 0
    last_ledger = time.monotonic()
    initial = loop.governor.evaluate(has_queued_work=loop.queue.has_runnable_work())
    last_state: GovernorState | None = initial.state
    heartbeat.write("running", initial.state.value, loop.governor.spinner.active_tier)
    _emit_daemon_event({"event": "daemon_started", "state": initial.state.value, "poll_s": poll_s})
    try:
        with _managed_stop_signals(stopper):
            while not stopper.is_set() and (max_ticks is None or ticks < max_ticks):
                ticks += 1
                last_state, last_ledger = _daemon_step(
                    loop, executor, heartbeat, ticks, last_state, last_ledger, ledger_interval_s
                )
                if max_ticks is not None and ticks >= max_ticks:
                    break
                stopper.wait(timeout=poll_s)
    finally:
        loop.governor.spinner.evict_all(loop.governor.sensor)
        heartbeat.write("stopped", loop.governor.state.value, None)
        lock.release()
        _emit_daemon_event({"event": "daemon_stopped", "ticks": ticks})
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ALOS Preemptible Local Compute Governor & Queue")
    parser.add_argument("--home", default=None, help="Portable ALOS_HOME root directory")
    parser.add_argument("--db-url", default=None, help="SQLAlchemy database URL override")
    parser.add_argument(
        "--mock",
        action="store_true",
        default=os.environ.get("ALOS_SWARM_MODE", "").lower() == "mock",
        help="Use deterministic mocked sensor and model spinner instead of live GPU/Ollama",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("bootstrap", help="Initialize ALOS_HOME, vault templates, and DB schema")
    doc_p = sub.add_parser("doctor", help="Verify runtime, DB, GPU, Ollama, and Docker readiness")
    doc_p.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    doc_p.add_argument("--require-ollama", action="store_true", help="Fail if Ollama is offline")
    sub.add_parser("status", help="Sample host sensors and print governor readiness JSON")
    enq = sub.add_parser("enqueue", help="Enqueue one local compute job or a JSON backlog file")
    enq.add_argument("--id", default=None, dest="job_id", help="Unique job identifier")
    enq.add_argument("--repo", default="alos", help="Target repository slug")
    enq.add_argument("--workflow", default="prompt", help="Workflow category label")
    enq.add_argument("--tier", default="fast_coder", help="Model capability tier")
    enq.add_argument("--priority", type=int, default=50, help="Base priority score")
    enq.add_argument("--requires-merge", action="store_true", help="Count against 3-PR merge cap")
    enq.add_argument("--allow-cloud-overflow", action="store_true", help="Allow overflow promotion")
    enq.add_argument("--max-tokens", type=int, default=None, help="Generation token cap")
    enq.add_argument("--prompt", default=None, help="Prompt or embedding input text")
    enq.add_argument("--file", default=None, help="Path to JSON array of backlog items")
    jobs_p = sub.add_parser("jobs", help="Inspect queue jobs filtered by state")
    jobs_p.add_argument("--state", default=None, help="Optional state filter")
    jobs_p.add_argument("--limit", type=int, default=25, help="Maximum rows to return")
    tick_p = sub.add_parser("tick", help="Run one governor + queue cycle and print result JSON")
    tick_p.add_argument("--keep-warm", action="store_true", help="Retain warm runner after tick")
    d_p = sub.add_parser("daemon", help="Run standing governor + queue loop with warm linger")
    d_p.add_argument("--poll-s", type=float, default=1.0)
    d_p.add_argument("--ledger-interval-s", type=float, default=300.0)
    d_p.add_argument("--max-ticks", type=int, default=None)
    led_p = sub.add_parser("ledger", help="Inspect recent capacity and thermal ledger rows")
    led_p.add_argument("--limit", type=int, default=10)
    return parser


def _dispatch_admin_cmd(
    args: argparse.Namespace, paths: RuntimePaths, db_url: str, mock_mode: bool
) -> int | None:
    if args.cmd == "bootstrap":
        print(json.dumps(bootstrap_home(home=paths.root, db_url=db_url)))
        return 0
    if args.cmd == "doctor":
        report = run_doctor(
            home=paths.root,
            db_url=db_url,
            require_ollama=bool(args.require_ollama),
            mock=mock_mode,
        )
        print(json.dumps(report))
        return 0 if report["healthy"] else 1
    if args.cmd == "ledger":
        print(json.dumps(query_ledger(db_url=db_url, limit=int(args.limit))))
        return 0
    if args.cmd == "jobs":
        print(json.dumps(query_jobs(db_url=db_url, state=args.state, limit=int(args.limit))))
        return 0
    return None


def _enqueue_batch_file(queue: StickyEpochQueue, file_path: str) -> int:
    items = json.loads(Path(file_path).read_text(encoding="utf-8"))
    created: list[str] = []
    for item in items:
        job = queue.enqueue(
            job_id=str(item["job_id"]),
            repo_slug=str(item.get("repo_slug", "alos")),
            workflow_type=str(item.get("workflow_type", "prompt")),
            model_tier=str(item.get("model_tier", "fast_coder")),
            priority=int(item.get("priority", 50)),
            requires_merge=bool(item.get("requires_merge", False)),
            allow_cloud_overflow=bool(item.get("allow_cloud_overflow", False)),
            payload=dict(item.get("payload") or {}),
        )
        created.append(job.job_id)
    print(json.dumps({"enqueued": len(created), "job_ids": created}))
    return 0


def _run_enqueue_cmd(args: argparse.Namespace, queue: StickyEpochQueue) -> int:
    try:
        if args.file:
            return _enqueue_batch_file(queue, str(args.file))
        if not args.job_id or args.prompt is None:
            print(
                json.dumps({"error": "missing_arguments", "detail": "--id and --prompt required"})
            )
            return 2
        payload: dict[str, Any] = {"prompt": str(args.prompt)}
        if args.max_tokens is not None:
            payload["max_tokens"] = int(args.max_tokens)
        job = queue.enqueue(
            job_id=str(args.job_id),
            repo_slug=str(args.repo),
            workflow_type=str(args.workflow),
            model_tier=str(args.tier),
            priority=int(args.priority),
            requires_merge=bool(args.requires_merge),
            allow_cloud_overflow=bool(args.allow_cloud_overflow),
            payload=payload,
        )
        print(json.dumps(asdict(job)))
        return 0
    except IntegrityError:
        print(json.dumps({"error": "duplicate_job_id", "job_id": args.job_id}))
        return 2


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for ALOS compute runtime, governor, queue, and ledger."""
    args = _build_parser().parse_args(argv)
    paths = RuntimePaths.resolve(args.home)
    db_url = paths.resolve_db_url(args.db_url)
    mock_mode = bool(args.mock)

    admin_rc = _dispatch_admin_cmd(args, paths, db_url, mock_mode)
    if admin_rc is not None:
        return admin_rc

    executor = mock_prompt_executor if mock_mode else default_prompt_executor
    loop = _build_default_stack(db_url, mock_mode=mock_mode)
    if args.cmd == "status":
        tr = loop.governor.evaluate(has_queued_work=loop.queue.has_runnable_work())
        print(
            json.dumps(
                {"state": tr.state.value, "reason": tr.reason, "snapshot": asdict(tr.snapshot)}
            )
        )
        return 0
    if args.cmd == "enqueue":
        return _run_enqueue_cmd(args, loop.queue)
    if args.cmd == "daemon":
        return _run_daemon(
            loop,
            executor=executor,
            paths=paths,
            poll_s=float(args.poll_s),
            ledger_interval_s=float(args.ledger_interval_s),
            max_ticks=args.max_ticks,
        )
    try:
        tick = loop.run_once(executor)
        print(
            json.dumps(
                {
                    "outcome": tick.outcome,
                    "state": tick.transition.state.value,
                    "job_id": tick.job_id,
                    "active_tier": tick.active_tier,
                }
            )
        )
    finally:
        if not args.keep_warm:
            loop.governor.spinner.evict_all(loop.governor.sensor)
    return 0


if __name__ == "__main__":
    sys.exit(main())
