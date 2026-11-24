"""Unit and integration tests for Spec 037: QueueHoldLatch, 404 fallback, and artifact burn."""

from __future__ import annotations

import io
import shutil
import subprocess
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from alos.db.session import DatabaseManager
from alos.runtime import (
    QueueHoldLatch,
    RuntimePaths,
    allocate_free_port,
    bootstrap_home,
    review_jobs,
)
from alos.swarm.burn import build_burn_executor
from alos.swarm.dispatcher import Ollama
from alos.swarm.governor import (
    GovernorState,
    HostGovernor,
    HysteresisConfig,
    ModelSpinner,
    ModelTierSpec,
)
from alos.swarm.queue import ComputeRuntimeLoop, PreemptedExecutionError, StickyEpochQueue
from alos.swarm.queue import main as queue_main
from alos.swarm.sensors import ScriptedSensor


class _MissingPrimarySpinner(ModelSpinner):
    """Test spinner where primary tag returns HTTP 404 and fallback succeeds."""

    def __init__(self, stock_empty: bool = False) -> None:
        super().__init__(
            port=allocate_free_port(),
            tiers={
                "reasoner": ModelTierSpec(
                    tier="reasoner",
                    model="missing-model:12b",
                    slots=2,
                    fallback_models=("installed-fallback:7b",),
                )
            },
        )
        self._stock_empty = stock_empty
        self.warmed_models: list[str] = []

    def _unload_stock_server(self) -> None:
        return None

    def _query_stock_model_sizes_mb(self) -> dict[str, int]:
        return {} if self._stock_empty else {"installed-fallback:7b": 4200}

    def _needs_server_restart(self, spec: ModelTierSpec) -> bool:
        return True

    def _stop_process_tree(self) -> bool:
        return True

    def _spawn_server(self, spec: ModelTierSpec) -> Ollama:
        return Ollama(self.host)

    def _warm_model(self, client: Ollama, spec: ModelTierSpec) -> str | None:
        self.warmed_models.append(spec.model)
        if spec.model.startswith("missing-"):
            err = urllib.error.HTTPError(
                self.host + "/api/generate",
                404,
                "Not Found",
                hdrs=None,  # type: ignore[arg-type]
                fp=io.BytesIO(b'{"error":"model not found"}'),
            )
            return self._classify_warm_http_error(err)
        return None


def _run_git(repo_dir: Path, *args: str) -> None:
    git_bin = shutil.which("git")
    assert git_bin is not None
    # Fixed argument list invoking resolved git binary inside isolated test tmp_path.
    subprocess.run(  # noqa: S603
        [git_bin, *args], cwd=repo_dir, check=True, capture_output=True, text=True
    )


def test_hold_latch_manual_and_idle_gate_and_force_override(tmp_path: Path) -> None:
    """FR-3701, FR-3702, FR-3704: Hold latch gates active desktop and --force overrides."""
    home = tmp_path / "home"
    boot = bootstrap_home(home=home)
    paths = RuntimePaths.resolve(home)
    db = DatabaseManager(db_url=boot["db_url"])
    q = StickyEpochQueue(db=db)
    q.enqueue("h1", "brandon-fox/alos", "prompt", "fast_coder", payload={"prompt": "hi"})

    sensor = ScriptedSensor()
    sensor.update(user_idle_seconds=12.0)
    spinner = MagicMock(spec=ModelSpinner)
    spinner.active_tier = None
    spinner.ensure_tier.return_value = Ollama()
    gov = HostGovernor(sensor=sensor, spinner=spinner)
    latch = QueueHoldLatch(paths.hold_file)
    loop = ComputeRuntimeLoop(governor=gov, queue=q, hold_latch=latch)

    # 1. Manual hold blocks even when idle is high
    latch.engage_manual("desk work")
    sensor.update(user_idle_seconds=900.0)
    res_manual = loop.run_once(lambda _j, _c, _e: {"ok": True})
    assert res_manual.outcome == "held"
    assert spinner.ensure_tier.call_count == 0

    # 2. Idle-gate hold blocks while active (20s < 300s) and blocks on fullscreen game
    latch.engage_idle_gate(min_idle_s=300.0, reason="stage while coding")
    sensor.update(user_idle_seconds=20.0, d3d_fullscreen=False)
    assert loop.run_once(lambda _j, _c, _e: {"ok": True}).outcome == "held_user_active"
    sensor.update(user_idle_seconds=400.0, d3d_fullscreen=True)
    assert loop.run_once(lambda _j, _c, _e: {"ok": True}).outcome == "held_user_active"

    # 3. Force mode bypasses hold latch and USER_PREEMPTED, but honors thermal cutoff
    sensor.update(d3d_fullscreen=True, gpu_temp_c=85.0)
    forced_hot = ComputeRuntimeLoop(governor=gov, queue=q, hold_latch=latch, force_gate=True)
    assert forced_hot.run_once(lambda _j, _c, _e: {"ok": True}).outcome == "gated"

    sensor.update(d3d_fullscreen=True, gpu_temp_c=45.0)
    gov.state = GovernorState.USER_PREEMPTED
    assert forced_hot.run_once(lambda _j, _c, _e: {"ok": True}).outcome == "completed"

    # 4. Remaining idle_gate clears once idle >= 300s without game
    q.enqueue("h2", "brandon-fox/alos", "prompt", "fast_coder", payload={"prompt": "hi2"})
    sensor.update(d3d_fullscreen=False, user_idle_seconds=315.0)
    gov.state = GovernorState.ARMED_IDLE
    assert loop.run_once(lambda _j, _c, _e: {"ok": True}).outcome == "completed"
    assert latch.read() is None


def test_missing_primary_model_steps_down_and_env_hysteresis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-3703, FR-3704: Missing primary model steps down via both tags and HTTP 404."""
    monkeypatch.setenv("ALOS_FOREIGN_VRAM_LIMIT_MB", "8192")
    monkeypatch.setenv("ALOS_PREEMPT_RECOVER_IDLE_S", "120")
    cfg = HysteresisConfig.from_env()
    assert cfg.foreign_vram_limit_mb == 8192
    assert cfg.preempt_recover_idle_s == 120.0

    spinner_tags = _MissingPrimarySpinner(stock_empty=False)
    spinner_tags.ensure_tier("reasoner")
    assert spinner_tags.active_model == "installed-fallback:7b"

    spinner_404 = _MissingPrimarySpinner(stock_empty=True)
    spinner_404.ensure_tier("reasoner")
    assert spinner_404.active_model == "installed-fallback:7b"
    assert spinner_404.warmed_models == ["missing-model:12b", "installed-fallback:7b"]


def test_artifact_burn_worktree_and_cli_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-3705..FR-3707: Burn writes deliverables, optional worktrees, sandbox hook, and review."""
    repo_dir = tmp_path / "sample_repo"
    repo_dir.mkdir()
    _run_git(repo_dir, "init", "-b", "main")
    _run_git(repo_dir, "config", "user.email", "t@e.com")
    _run_git(repo_dir, "config", "user.name", "Tester")
    _run_git(repo_dir, "config", "commit.gpgsign", "false")
    (repo_dir / "README.md").write_text("# Sample\n", encoding="utf-8")
    _run_git(repo_dir, "add", "README.md")
    _run_git(repo_dir, "commit", "-m", "init")

    home = tmp_path / "alos_home"
    boot = bootstrap_home(home=home)
    paths = RuntimePaths.resolve(home)
    db = DatabaseManager(db_url=boot["db_url"])
    q = StickyEpochQueue(db=db)
    q.enqueue(
        "nectr-ca4",
        "brandon-fox/nectR",
        "test_draft",
        "fast_coder",
        requires_merge=True,
        payload={
            "title": "CA4 Guard Bee cross-hive registration",
            "source_ref": "openspec/changes/harden-authority-and-accounting/tasks.md#CA4",
            "prompt": "Draft Guard Bee cross-hive test.",
            "create_worktree_branch": True,
            "verify_in_sandbox": True,
            "local_repo_path": str(repo_dir),
        },
    )

    monkeypatch.setattr(
        "alos.swarm.sandbox.run_draft",
        lambda *_a, **_kw: {"state": "passed", "passed": 2},
    )
    executor = build_burn_executor(paths=paths, mock_mode=True)
    leased = q.lease_next()
    assert leased is not None
    with pytest.raises(PreemptedExecutionError):
        executor(leased, Ollama(), MagicMock(is_set=lambda: True))
    res = executor(leased, Ollama(), MagicMock(is_set=lambda: False))
    q.complete_job(leased.job_id, result_json=res)

    artifact = Path(res["artifact_path"])
    assert artifact.exists()
    assert res["sandbox_state"] == "passed"
    assert (paths.results_dir / "burn_digest.md").exists()
    assert (paths.vault_dir / "Bus" / "Results" / "nectr-ca4.md").exists()
    assert res["worktree_branch"] == "alos-burn/nectr-ca4"
    assert Path(res["worktree_path"]).exists()

    assert queue_main(["--home", str(home), "--mock", "pause", "--arm-after-idle", "180"]) == 0
    assert paths.hold_file.exists()
    assert queue_main(["--home", str(home), "--mock", "tick"]) == 0
    assert queue_main(["--home", str(home), "--mock", "resume"]) == 0
    assert not paths.hold_file.exists()
    assert (
        queue_main(
            [
                "--home",
                str(home),
                "--mock",
                "review",
                "--repo",
                "brandon-fox/nectR",
                "--approve-all",
            ]
        )
        == 0
    )
    reviewed = review_jobs(db_url=boot["db_url"], job_id="nectr-ca4", action="approve")
    assert reviewed["updated"] == 0

    # Plain prompt delegation + live-mode burn delegation + requeue review path
    q.enqueue("plain-1", "brandon-fox/alos", "prompt", "fast_coder", payload={"prompt": "ping"})
    plain_leased = q.lease_next()
    assert plain_leased is not None
    assert (
        "MOCK_OK" in executor(plain_leased, Ollama(), MagicMock(is_set=lambda: False))["response"]
    )
    q.complete_job("plain-1")

    monkeypatch.setattr(
        "alos.swarm.queue.default_prompt_executor",
        lambda *_a, **_kw: {"response": "LIVE_OK", "model": "qwen2.5-coder:7b", "eval_count": 12},
    )
    q.enqueue(
        "live-deliv",
        "brandon-fox/alos",
        "review_fix",
        "fast_coder",
        requires_merge=True,
        payload={"title": "Fix lint", "create_worktree_branch": True, "local_repo_path": ""},
    )
    live_leased = q.lease_next()
    assert live_leased is not None
    live_exec = build_burn_executor(paths=paths, mock_mode=False)
    live_res = live_exec(live_leased, Ollama(), MagicMock(is_set=lambda: False))
    assert live_res["response"] == "LIVE_OK"
    q.complete_job("live-deliv", result_json=live_res)
    requeued = review_jobs(db_url=boot["db_url"], job_id="live-deliv", action="requeue")
    assert requeued["target_state"] == "queued"
