"""Unit and integration tests for Spec 037: QueueHoldLatch, 404 fallback, and artifact burn."""

from __future__ import annotations

import io
import json
import subprocess
import urllib.error
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from alos.db.session import DatabaseManager
from alos.runtime import QueueHoldLatch, RuntimePaths, allocate_free_port, bootstrap_home, review_jobs
from alos.swarm.burn import build_burn_executor
from alos.swarm.dispatcher import Ollama
from alos.swarm.governor import (
    GovernorState,
    HostGovernor,
    HysteresisConfig,
    ModelSpinner,
    ModelTierSpec,
)
from alos.swarm.queue import ComputeRuntimeLoop, StickyEpochQueue, main as queue_main
from alos.swarm.sensors import ScriptedSensor


class _MissingPrimarySpinner(ModelSpinner):
    """Test spinner where primary tag returns HTTP 404 and fallback succeeds."""

    def __init__(self) -> None:
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
        self.warmed_models: list[str] = []

    def _unload_stock_server(self) -> None:
        return None

    def _query_stock_model_sizes_mb(self) -> dict[str, int]:
        return {"installed-fallback:7b": 4200}

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


def test_hold_latch_manual_and_idle_gate_and_force_override(tmp_path: Path) -> None:
    """FR-3701, FR-3702, FR-3704: Hold latch gates active desktop and --force overrides non-thermal blocks."""
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

    # 3. Force mode bypasses hold latch and foreign-VRAM USER_PREEMPTED, but still honors thermal cutoff
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


def test_missing_primary_model_steps_down_and_env_hysteresis(monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-3703, FR-3704: Missing primary model steps down to fallback; env overrides VRAM limit."""
    monkeypatch.setenv("ALOS_FOREIGN_VRAM_LIMIT_MB", "8192")
    monkeypatch.setenv("ALOS_PREEMPT_RECOVER_IDLE_S", "120")
    cfg = HysteresisConfig.from_env()
    assert cfg.foreign_vram_limit_mb == 8192
    assert cfg.preempt_recover_idle_s == 120.0

    spinner = _MissingPrimarySpinner()
    spinner.ensure_tier("reasoner")
    assert spinner.active_model == "installed-fallback:7b"


def test_artifact_burn_worktree_and_cli_commands(tmp_path: Path) -> None:
    """FR-3705, FR-3706, FR-3707: Burn writes Markdown deliverables, optional git worktree, and review CLI."""
    repo_dir = tmp_path / "sample_repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@e.com"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo_dir, check=True)
    (repo_dir / "README.md").write_text("# Sample\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_dir, check=True, capture_output=True)

    home = tmp_path / "alos_home"
    boot = bootstrap_home(home=home)
    paths = RuntimePaths.resolve(home)
    db = DatabaseManager(db_url=boot["db_url"])
    q = StickyEpochQueue(db=db)
    q.enqueue(
        "nectr-ca4",
        "brandon-fox/nectR",
        "task_patch",
        "fast_coder",
        requires_merge=True,
        payload={
            "title": "CA4 Guard Bee cross-hive registration",
            "source_ref": "openspec/changes/harden-authority-and-accounting/tasks.md#CA4",
            "prompt": "Draft Guard Bee cross-hive patch plan and diff.",
            "create_worktree_branch": True,
            "local_repo_path": str(repo_dir),
        },
    )

    executor = build_burn_executor(paths=paths, mock_mode=True)
    leased = q.lease_next()
    assert leased is not None
    res = executor(leased, Ollama(), MagicMock(is_set=lambda: False))
    q.complete_job(leased.job_id, result_json=res)

    artifact = Path(res["artifact_path"])
    assert artifact.exists()
    assert "CA4 Guard Bee" in artifact.read_text(encoding="utf-8")
    assert (paths.results_dir / "burn_digest.md").exists()
    assert (paths.vault_dir / "Bus" / "Results" / "nectr-ca4.md").exists()
    assert res["worktree_branch"] == "alos-burn/nectr-ca4"
    assert Path(res["worktree_path"]).exists()

    # CLI pause, resume, review, and burn smoke verification
    assert queue_main(["--home", str(home), "--mock", "pause", "--arm-after-idle", "180"]) == 0
    assert (paths.hold_file).exists()
    assert queue_main(["--home", str(home), "--mock", "tick"]) == 0
    assert queue_main(["--home", str(home), "--mock", "resume"]) == 0
    assert not (paths.hold_file).exists()
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
    assert reviewed["updated"] == 0  # already approved via CLI above
