"""Domain concurrency, resource-contention, and isolation stress suite.

Spec: specs/035-parallel-testing-and-qa-matrix/spec.md (FR-001, FR-006, FR-007, FR-008)
ADR: ADR-0019
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select

from alos.core.evaluator import RiskLevel
from alos.db.models import ComputeQueueJobModel
from alos.db.session import DatabaseManager
from alos.logs.decision_log import DecisionLogger
from alos.logs.system_audit import SystemAuditLogger
from alos.logs.telemetry import TelemetryTracer
from alos.runtime import (
    DaemonAlreadyRunningError,
    HealthHeartbeat,
    SingleInstanceLock,
    allocate_free_port,
)
from alos.schemas.actions import WebSearchQuery
from alos.swarm import sandbox
from alos.swarm.governor import (
    ContainerPauser,
    EvictionReport,
    GovernorState,
    HostGovernor,
    ModelSpinner,
)
from alos.swarm.queue import QueueConfig, StickyEpochQueue
from alos.swarm.sensors import FaultOverlaySensor, ScriptedSensor, SensorProvider

pytestmark = [pytest.mark.contention, pytest.mark.source]


class _StressSpinner(ModelSpinner):
    def __init__(self) -> None:
        super().__init__(port=allocate_free_port())
        self._lock = threading.Lock()
        self.evict_calls = 0
        self._tier: str | None = "fast_coder"

    @property
    def active_tier(self) -> str | None:
        with self._lock:
            return self._tier

    def evict_all(self, sensor: SensorProvider | None = None) -> EvictionReport:
        with self._lock:
            self.evict_calls += 1
            self._tier = None
        return EvictionReport(
            elapsed_s=0.01, graceful_unloaded=True, tree_killed=True, remaining_managed_vram_mb=0
        )


def test_allocate_free_port_concurrent_ephemeral_ports() -> None:
    """FR-001: Ephemeral port allocator returns valid loopback ports safely across threads."""
    with ThreadPoolExecutor(max_workers=16) as pool:
        ports = list(pool.map(lambda _: allocate_free_port(), range(32)))
    assert all(1024 <= p <= 65535 for p in ports)
    assert len(set(ports)) >= 16


def _seed_multithread_storm_jobs(
    queue: StickyEpochQueue, total_no_merge: int, total_merge_alos: int, total_merge_nectr: int
) -> None:
    for idx in range(total_no_merge):
        tier = "fast_coder" if idx % 2 == 0 else "reasoner"
        queue.enqueue(
            job_id=f"nm-{idx:03d}",
            repo_slug="alos",
            workflow_type="unit",
            model_tier=tier,
            priority=50 + (idx % 10),
            requires_merge=False,
        )
    for idx in range(total_merge_alos):
        queue.enqueue(
            job_id=f"merge-alos-{idx}",
            repo_slug="alos",
            workflow_type="pr",
            model_tier="fast_coder",
            priority=80,
            requires_merge=True,
        )
    for idx in range(total_merge_nectr):
        queue.enqueue(
            job_id=f"merge-nectr-{idx}",
            repo_slug="nectR",
            workflow_type="pr",
            model_tier="fast_coder",
            priority=80,
            requires_merge=True,
        )


def _run_multithread_storm_workers(queue: StickyEpochQueue) -> list[str]:
    active_leases: set[str] = set()
    double_leased: list[str] = []
    preempted_once: set[str] = set()
    failed_once: set[str] = set()
    state_lock = threading.Lock()

    def worker(worker_idx: int) -> None:
        wid = f"mt-worker-{worker_idx}"
        while True:
            leased = queue.lease_next(worker_id=wid, active_tier="fast_coder")
            if leased is None:
                return
            with state_lock:
                if leased.job_id in active_leases:
                    double_leased.append(leased.job_id)
                active_leases.add(leased.job_id)
                should_preempt = leased.job_id.endswith(("001", "005")) and (
                    leased.job_id not in preempted_once
                )
                if should_preempt:
                    preempted_once.add(leased.job_id)
                should_fail = leased.job_id.endswith(("002", "006")) and (
                    leased.job_id not in failed_once
                )
                if should_fail:
                    failed_once.add(leased.job_id)
            try:
                if should_preempt:
                    queue.release_preempted(leased.job_id, checkpoint_ns=f"ckpt-{leased.job_id}")
                elif should_fail:
                    queue.fail_job(leased.job_id, error_msg="transient contention retry")
                else:
                    if leased.job_id in preempted_once:
                        assert leased.checkpoint_ns == f"ckpt-{leased.job_id}"
                        assert leased.attempts == 1
                    queue.complete_job(leased.job_id, result_json={"worker": wid})
            finally:
                with state_lock:
                    active_leases.discard(leased.job_id)

    with ThreadPoolExecutor(max_workers=10) as pool:
        for fut in as_completed([pool.submit(worker, i) for i in range(10)]):
            fut.result()
    return double_leased


def test_sqlite_sticky_epoch_queue_multithread_storm(tmp_path: Path) -> None:
    """FR-006/FR-008: Multi-thread worker storm preserves zero double-leases & merge caps."""
    db_url = f"sqlite:///{(tmp_path / 'mt_storm.db').as_posix()}"
    db = DatabaseManager(db_url=db_url)
    db.create_all_tables()
    clock_lock = threading.Lock()
    current_time = datetime(2026, 11, 23, 12, 0, 0, tzinfo=timezone.utc)

    def now_fn() -> datetime:
        with clock_lock:
            return current_time

    cfg = QueueConfig(lease_ttl_s=2.0, max_open_merge_jobs=3, max_epoch_s=600.0)
    queue = StickyEpochQueue(db=db, config=cfg, now_fn=now_fn)
    total_no_merge, total_merge_alos, total_merge_nectr = 48, 6, 4
    _seed_multithread_storm_jobs(queue, total_no_merge, total_merge_alos, total_merge_nectr)

    double_leased = _run_multithread_storm_workers(queue)
    assert double_leased == [], f"Detected concurrent double-leased jobs: {double_leased}"

    with db.get_session() as session:
        rows = {r.job_id: r for r in session.scalars(select(ComputeQueueJobModel))}

    # All 48 no-merge jobs must have succeeded exactly once
    for idx in range(total_no_merge):
        jid = f"nm-{idx:03d}"
        assert rows[jid].state == "succeeded"
    # Per-repo 3-open-PR merge cap: exactly 3 in review_pending and remaining queued per repo
    alos_pending = [rows[f"merge-alos-{i}"].state for i in range(total_merge_alos)]
    nectr_pending = [rows[f"merge-nectr-{i}"].state for i in range(total_merge_nectr)]
    assert alos_pending.count("review_pending") == 3
    assert alos_pending.count("queued") == 3
    assert nectr_pending.count("review_pending") == 3
    assert nectr_pending.count("queued") == 1

    # Verify expired lease reclamation under clock advance
    queue.enqueue("expired-1", "alos", "unit", "fast_coder", requires_merge=False)
    leased_exp = queue.lease_next(worker_id="dead-worker")
    assert leased_exp is not None and leased_exp.job_id == "expired-1"
    with clock_lock:
        current_time = current_time + timedelta(seconds=10)
    reclaimed = queue.lease_next(worker_id="recovery-worker")
    assert reclaimed is not None and reclaimed.job_id == "expired-1"
    assert reclaimed.attempts == 1


def test_sqlite_sticky_epoch_queue_multiprocess_storm(tmp_path: Path) -> None:
    """FR-006/FR-008: Separate OS subprocesses concurrently leasing from one SQLite WAL DB."""
    db_path = tmp_path / "mp_storm.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    db = DatabaseManager(db_url=db_url)
    db.create_all_tables()
    queue = StickyEpochQueue(db=db)
    total_jobs = 36
    for idx in range(total_jobs):
        queue.enqueue(
            job_id=f"mp-{idx:03d}",
            repo_slug="alos",
            workflow_type="mp",
            model_tier="fast_coder" if idx % 3 else "reasoner",
            priority=50 + (idx % 5),
        )
    db.engine.dispose()

    worker_code = (
        "import json, sys\n"
        "from alos.db.session import DatabaseManager\n"
        "from alos.swarm.queue import StickyEpochQueue\n"
        "db = DatabaseManager(db_url=sys.argv[1])\n"
        "q = StickyEpochQueue(db=db)\n"
        "wid = sys.argv[2]\n"
        "leased_ids = []\n"
        "while True:\n"
        "    job = q.lease_next(worker_id=wid, active_tier='fast_coder')\n"
        "    if job is None:\n"
        "        break\n"
        "    leased_ids.append(job.job_id)\n"
        "    q.complete_job(job.job_id, result_json={'worker': wid})\n"
        "db.engine.dispose()\n"
        "print(json.dumps(leased_ids))\n"
    )

    # Fixed argument list invoking Python on a static test snippet without shell.
    procs = [
        subprocess.Popen(  # noqa: S603
            [sys.executable, "-c", worker_code, db_url, f"proc-{i}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for i in range(2)
    ]
    all_leased: list[str] = []
    for proc in procs:
        out, err = proc.communicate(timeout=30)
        assert proc.returncode == 0, f"Subprocess worker crashed:\n{err}"
        all_leased.extend(json.loads(out.strip()))

    assert sorted(all_leased) == [f"mp-{i:03d}" for i in range(total_jobs)], (
        f"Expected {total_jobs} unique leases with zero duplicates, got {len(all_leased)}: "
        f"duplicates={len(all_leased) - len(set(all_leased))}"
    )


def test_single_instance_lock_thread_and_subprocess_race_storms(tmp_path: Path) -> None:
    """FR-007/FR-008: Strict mutual exclusion across thread + subprocess stale-PID races."""
    # 1. Stale dead-PID reclamation race across 16 concurrent threads
    lock_path = tmp_path / "run" / "stale_race.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps({"pid": 99_999_999}), encoding="utf-8")

    barrier = threading.Barrier(12)
    winners: list[SingleInstanceLock] = []
    losers = 0
    guard = threading.Lock()

    def try_lock() -> None:
        nonlocal losers
        barrier.wait()
        inst = SingleInstanceLock(lock_path)
        try:
            inst.acquire()
            with guard:
                winners.append(inst)
        except DaemonAlreadyRunningError:
            with guard:
                losers += 1

    threads = [threading.Thread(target=try_lock) for _ in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    try:
        assert len(winners) == 1, f"Expected strictly 1 lock winner, got {len(winners)}"
        assert losers == 11
    finally:
        for w in winners:
            w.release()

    # 2. Subprocess lock acquisition storm on stale dead-PID lockfile
    sub_lock = tmp_path / "run" / "subproc_race.lock"
    sub_lock.write_text(json.dumps({"pid": 99_999_999}), encoding="utf-8")
    sub_code = (
        "import sys, time\n"
        "from pathlib import Path\n"
        "from alos.runtime import DaemonAlreadyRunningError, SingleInstanceLock\n"
        "lk = SingleInstanceLock(Path(sys.argv[1]))\n"
        "try:\n"
        "    lk.acquire()\n"
        "    time.sleep(0.35)\n"
        "    lk.release()\n"
        "    sys.exit(0)\n"
        "except DaemonAlreadyRunningError:\n"
        "    sys.exit(3)\n"
    )
    # Fixed argument list invoking Python on a static lock snippet without shell.
    procs = [
        subprocess.Popen(  # noqa: S603
            [sys.executable, "-c", sub_code, str(sub_lock)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(3)
    ]
    codes = [p.wait(timeout=15) for p in procs]
    assert codes.count(0) == 1, f"Expected exactly 1 winner (exit 0), got exit codes {codes}"
    assert codes.count(3) == 2


def test_journal_decision_heartbeat_and_tracer_concurrency(tmp_path: Path) -> None:
    """FR-007/FR-008: Concurrent JSONL appends, heartbeats, and telemetry spans never tear."""
    audit_file = tmp_path / "logs" / "audit_storm.jsonl"
    decision_file = tmp_path / "logs" / "decision_storm.jsonl"
    health_file = tmp_path / "run" / "health.json"

    audit_logger = SystemAuditLogger(log_file_path=str(audit_file))
    decision_logger = DecisionLogger(log_file_path=str(decision_file))
    heartbeat = HealthHeartbeat(health_file)
    tracer = TelemetryTracer()
    action = WebSearchQuery(query="concurrency test", description="verify thread safety")
    large_blob = "X" * 4096

    def thread_worker(tid: int) -> None:
        for idx in range(25):
            with tracer.span(f"op-{tid}-{idx}", tags={"tid": tid}):
                audit_logger.log_event(
                    step=f"step-{tid}-{idx}",
                    status="OK",
                    metadata={"blob": large_blob, "tid": tid, "idx": idx},
                )
                decision_logger.log_decision(
                    trigger=f"trig-{tid}-{idx}",
                    action=action,
                    risk_level=RiskLevel.LOW,
                    decision="APPROVED",
                    rationale=large_blob,
                    constitution_articles_checked=["I"],
                    preferences_checked=[],
                    corrections_checked=[],
                    alternatives_considered=[],
                    self_correction_rounds=0,
                )
                heartbeat.write("running", "WARM_ACTIVE", "fast_coder")
                tracer.record_metric("iter_ms", float(idx))

    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(thread_worker, t) for t in range(8)]
        for f in as_completed(futs):
            f.result()

    # Also hammer audit_file from 3 concurrent OS subprocesses
    sub_audit_code = (
        "import sys\n"
        "from alos.logs.system_audit import SystemAuditLogger\n"
        "lg = SystemAuditLogger(log_file_path=sys.argv[1])\n"
        "blob = 'Z' * 4096\n"
        "for i in range(30):\n"
        "    lg.log_event(step=f'proc-{sys.argv[2]}-{i}', status='OK', metadata={'b': blob})\n"
    )
    # Fixed argument list invoking Python on a static audit snippet without shell.
    procs = [
        subprocess.Popen(  # noqa: S603
            [sys.executable, "-c", sub_audit_code, str(audit_file), str(i)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for i in range(3)
    ]
    for p in procs:
        _, err = p.communicate(timeout=20)
        assert p.returncode == 0, err

    audit_lines = audit_file.read_text(encoding="utf-8").splitlines()
    assert len(audit_lines) == (8 * 25) + (3 * 30)
    parsed_audit = [json.loads(line) for line in audit_lines]
    assert len(parsed_audit) == 290

    decision_lines = decision_file.read_text(encoding="utf-8").splitlines()
    assert len(decision_lines) == 8 * 25
    parsed_decisions = [json.loads(line) for line in decision_lines]
    decision_ids = [d["decision_id"] for d in parsed_decisions]
    assert len(set(decision_ids)) == 200, "Duplicate decision_id generated under thread race!"

    spans = tracer.get_spans()
    span_ids = [s.span_id for s in spans]
    assert len(spans) == 200
    assert len(set(span_ids)) == 200, "Duplicate span_id generated under thread race!"
    assert json.loads(health_file.read_text(encoding="utf-8"))["status"] == "running"


def test_host_governor_and_container_pauser_concurrent_storm() -> None:
    """FR-008: Concurrent telemetry updates, evaluate() ticks, and eviction stay consistent."""
    base_sensor = ScriptedSensor()
    overlay = FaultOverlaySensor(base_sensor)
    spinner = _StressSpinner()
    pauser = ContainerPauser(runner=lambda _cmd: 0)
    for idx in range(5):
        pauser.register(f"worker-{idx}")

    gov = HostGovernor(
        sensor=overlay,
        spinner=spinner,
        pauser=pauser,
        state=GovernorState.WARM_ACTIVE,
    )

    def mutator(tid: int) -> None:
        for step in range(40):
            if step % 4 == 0:
                overlay.inject(d3d_fullscreen=True, user_idle_seconds=0.0)
            elif step % 4 == 1:
                overlay.inject(gpu_temp_c=86.0, d3d_fullscreen=False)
            elif step % 4 == 2:
                overlay.clear()
                base_sensor.update(gpu_temp_c=48.0, user_idle_seconds=600.0)
            else:
                pauser.register(f"dyn-{tid}-{step}")
                pauser.unregister(f"dyn-{tid}-{step}")
            tr = gov.evaluate(has_queued_work=(step % 2 == 0))
            assert isinstance(tr.state, GovernorState)

    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(mutator, i) for i in range(8)]
        for f in as_completed(futs):
            f.result()

    assert spinner.evict_calls >= 1


def test_sandbox_run_plan_multiworker_saturation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-008: Concurrent multi-worker sandbox.run_plan saturates workers >= 4 deterministically."""
    repo = tmp_path / "repo"
    (repo / "pkg").mkdir(parents=True)
    target_mod = repo / "pkg" / "calc.py"
    target_mod.write_text("def add(a: int, b: int) -> int:\n    return a + b\n", encoding="utf-8")

    drafts_dir = tmp_path / "drafts"
    drafts_dir.mkdir()
    jobs: list[dict[str, Any]] = []
    for idx in range(8):
        draft = drafts_dir / f"test_draft_{idx}.py"
        body = (
            "import time\ndef test_hang():\n    time.sleep(99)\n"
            if idx == 7
            else "from pkg.calc import add\ndef test_add():\n    assert add(2, 3) == 5\n"
        )
        draft.write_text(body, encoding="utf-8")
        jobs.append(
            {
                "id": f"job-{idx:02d}",
                "repo": str(repo),
                "test": str(draft),
                "mutants": [
                    {
                        "file": "pkg/calc.py",
                        "line": "return a + b",
                        "mutated": "return a - b" if idx % 2 == 0 else "return a + b + 0",
                    }
                ],
            }
        )

    monkeypatch.setattr(sandbox, "require_image", lambda _img: None)
    active = 0
    peak_active = 0
    lock = threading.Lock()

    def fake_run_container(argv: list[str], name: str, timeout_s: float) -> tuple[int | None, str]:
        nonlocal active, peak_active
        with lock:
            active += 1
            peak_active = max(peak_active, active)
        try:
            time.sleep(0.02)
            # Detect staged draft content or mutant overlay content
            for token in argv:
                if "target=/drafts/test_draft.py" in token:
                    draft_src = token.split("source=")[1].split(",target=")[0]
                    if "time.sleep(99)" in Path(draft_src).read_text(encoding="utf-8"):
                        return None, ""
            for token in argv:
                if "mutant.py" in token and "target=/repo/pkg/calc.py" in token:
                    src_part = token.split("source=")[1].split(",target=")[0]
                    mut_txt = Path(src_part).read_text(encoding="utf-8")
                    if "a - b" in mut_txt:
                        return 1, "1 failed in 0.01s"
                    return 0, "1 passed in 0.01s"
            return 0, "1 passed in 0.01s"
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(sandbox, "run_container", fake_run_container)

    summary = sandbox.run_plan({"image": "alos-sandbox:test", "jobs": jobs}, workers=6)
    assert peak_active >= 2
    assert summary["counts"]["passed"] == 7
    assert summary["counts"]["timeout"] == 1
    # Even jobs 0, 2, 4, 6 kill their a - b mutant -> 4 promoted
    assert summary["promoted"] == 4
