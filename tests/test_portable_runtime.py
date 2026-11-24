"""Unit tests for portable production runtime, PID locks, health heartbeats, and unified CLI.

Spec: specs/032-portable-production-runtime/spec.md
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

import pytest

from alos.cli import main as alos_cli_main
from alos.runtime import (
    DaemonAlreadyRunningError,
    HealthHeartbeat,
    RuntimePaths,
    SingleInstanceLock,
    bootstrap_home,
    is_pid_alive,
    query_ledger,
    run_doctor,
)
from alos.swarm.queue import _build_default_stack, _run_daemon, mock_prompt_executor


def test_runtime_paths_and_db_url_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify RuntimePaths resolves explicit home, ALOS_HOME env, and POSIX SQLite URLs."""
    monkeypatch.delenv("ALOS_QUEUE_DB_URL", raising=False)
    explicit = RuntimePaths.resolve(tmp_path / "custom_home")
    assert explicit.root == (tmp_path / "custom_home").resolve()
    assert explicit.resolve_db_url().startswith("sqlite:///")
    assert "\\" not in explicit.resolve_db_url()

    monkeypatch.setenv("ALOS_HOME", str(tmp_path / "env_home"))
    from_env = RuntimePaths.resolve()
    assert from_env.root == (tmp_path / "env_home").resolve()

    monkeypatch.setenv("ALOS_QUEUE_DB_URL", "sqlite:///override.db")
    assert from_env.resolve_db_url() == "sqlite:///override.db"


def test_single_instance_lock_blocks_live_pid_and_reclaims_dead_pid(tmp_path: Path) -> None:
    """Active PID lock rejects duplicate daemons; stale dead-PID lock is reclaimed."""
    assert is_pid_alive(os.getpid()) is True
    assert is_pid_alive(-5) is False
    assert is_pid_alive(99_999_999) is False

    lock_file = tmp_path / "run" / "governor.lock"
    with SingleInstanceLock(lock_file):
        assert lock_file.exists()
        with pytest.raises(DaemonAlreadyRunningError, match="already running"):
            SingleInstanceLock(lock_file).acquire()
    assert not lock_file.exists()

    # Write stale dead-PID lockfile and verify reclamation
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file.write_text(json.dumps({"pid": 99_999_999}), encoding="utf-8")
    with SingleInstanceLock(lock_file):
        data = json.loads(lock_file.read_text(encoding="utf-8"))
        assert data["pid"] == os.getpid()


def test_bootstrap_idempotency_doctor_and_heartbeat(tmp_path: Path) -> None:
    """bootstrap_home seeds templates once, preserves user edits, and passes run_doctor."""
    home = tmp_path / "portable_alos"
    first = bootstrap_home(home=home)
    assert first["status"] == "bootstrapped"
    assert set(first["seeded_vault_files"]) == {
        "USER_PROFILE.md",
        "PREFERENCES.md",
        "CORRECTION_LEDGER.md",
    }
    assert (home / "alos.env").exists()

    profile = home / "vault" / "USER_PROFILE.md"
    profile.write_text("# Custom Profile\n", encoding="utf-8")
    second = bootstrap_home(home=home)
    assert second["seeded_vault_files"] == []
    assert profile.read_text(encoding="utf-8") == "# Custom Profile\n"

    doc_ok = run_doctor(home=home, mock=True)
    assert doc_ok["healthy"] is True

    doc_offline = run_doctor(
        home=home, ollama_host="http://127.0.0.1:11491", require_ollama=True, mock=False
    )
    assert doc_offline["healthy"] is False

    hb = HealthHeartbeat(home / "run" / "health.json")
    hb.write("running", "WARM_ACTIVE", "fast_coder")
    saved = json.loads((home / "run" / "health.json").read_text(encoding="utf-8"))
    assert saved["status"] == "running"
    assert saved["active_tier"] == "fast_coder"


def test_daemon_stop_event_lock_contention_and_unified_cli(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify graceful stop_event shutdown, lock exit code 3, ledger query, and unified alos CLI."""
    home = tmp_path / "cli_home"
    paths = RuntimePaths.resolve(home)
    db_url = paths.resolve_db_url()

    with pytest.raises(SystemExit) as b_exc:
        alos_cli_main(["--home", str(home), "--mock", "bootstrap"])
    assert b_exc.value.code == 0

    with pytest.raises(SystemExit) as d_exc:
        alos_cli_main(["--home", str(home), "--mock", "doctor", "--json"])
    assert d_exc.value.code == 0

    with pytest.raises(SystemExit) as e_exc:
        alos_cli_main(
            [
                "--home",
                str(home),
                "--mock",
                "enqueue",
                "--id",
                "p-1",
                "--prompt",
                "portable check",
            ]
        )
    assert e_exc.value.code == 0

    # Stop event wakes daemon cleanly and writes stopped health.json
    loop = _build_default_stack(db_url, mock_mode=True)
    stopper = threading.Event()
    threading.Timer(0.05, stopper.set).start()
    rc = _run_daemon(
        loop,
        executor=mock_prompt_executor,
        paths=paths,
        poll_s=5.0,
        ledger_interval_s=1.0,
        max_ticks=None,
        stop_event=stopper,
    )
    assert rc == 0
    health = json.loads(paths.health_file.read_text(encoding="utf-8"))
    assert health["status"] == "stopped"
    assert len(query_ledger(db_url, limit=5)) >= 1

    # Duplicate daemon while lock is held exits with code 3
    with SingleInstanceLock(paths.lock_file):
        rc_locked = _run_daemon(
            loop,
            executor=mock_prompt_executor,
            paths=paths,
            poll_s=0.1,
            ledger_interval_s=10.0,
            max_ticks=1,
        )
        assert rc_locked == 3

    with pytest.raises(SystemExit) as l_exc:
        alos_cli_main(["--home", str(home), "--mock", "ledger", "--limit", "3"])
    assert l_exc.value.code == 0
    _ = capsys.readouterr()

    # Shorthand direct query delegates to dual-loop reasoning graph
    alos_cli_main(["Plan focus time tomorrow", "--vault", str(paths.vault_dir)])
    out = capsys.readouterr().out
    assert "final_status" in out or "query" in out


def test_commit_aware_candidate_selection_steps_down_under_tight_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify ModelSpinner skips oversized models when Windows OS commit headroom is tight."""
    from alos.swarm import governor as gov_mod
    from alos.swarm.governor import DEFAULT_MODEL_TIERS, ModelSpinner

    spinner = ModelSpinner(port=11493)
    spec = DEFAULT_MODEL_TIERS["fast_coder"]
    sizes_mb = {
        "qwen2.5-coder:7b-instruct": 4480,
        "qwen2.5-coder:3b": 1840,
        "qwen2.5-coder:1.5b": 940,
        "qwen2.5-coder:0.5b": 378,
    }

    monkeypatch.setattr(gov_mod, "query_win32_free_commit_mb", lambda: 7000)
    plenty = spinner._select_commit_fitting_candidate(
        spec, ["qwen2.5-coder:3b", "qwen2.5-coder:1.5b", "qwen2.5-coder:0.5b"], sizes_mb
    )
    assert plenty.model == "qwen2.5-coder:7b-instruct"

    monkeypatch.setattr(gov_mod, "query_win32_free_commit_mb", lambda: 2600)
    medium_q = ["qwen2.5-coder:3b", "qwen2.5-coder:1.5b", "qwen2.5-coder:0.5b"]
    medium = spinner._select_commit_fitting_candidate(spec, medium_q, sizes_mb)
    assert medium.model == "qwen2.5-coder:1.5b"
    assert medium_q == ["qwen2.5-coder:0.5b"]

    monkeypatch.setattr(gov_mod, "query_win32_free_commit_mb", lambda: 900)
    tight_q = ["qwen2.5-coder:3b", "qwen2.5-coder:1.5b", "qwen2.5-coder:0.5b"]
    tight = spinner._select_commit_fitting_candidate(spec, tight_q, sizes_mb)
    assert tight.model == "qwen2.5-coder:0.5b"
    assert tight.slots == 1
    assert tight.num_ctx == 2048


def test_backlog_bug_regressions_ensure_tier_fail_batch_cli_and_jobs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Regression suite for bugs discovered during the 10-item live backlog burn-down."""
    home = tmp_path / "reg_home"
    paths = RuntimePaths.resolve(home)
    db_url = paths.resolve_db_url()

    # BUG-005: `alos --help` lists runtime/governor commands
    with pytest.raises(SystemExit) as h_exc:
        alos_cli_main(["--help"])
    assert h_exc.value.code == 0
    help_out = capsys.readouterr().out
    for cmd in ("bootstrap", "doctor", "status", "enqueue", "jobs", "daemon", "ledger"):
        assert cmd in help_out

    # BUG-007: batch `--file` backlog loader + `alos jobs` inspection
    batch_file = tmp_path / "batch.json"
    batch_file.write_text(
        json.dumps(
            [
                {
                    "job_id": "b-1",
                    "repo_slug": "alos",
                    "workflow_type": "bugfix",
                    "model_tier": "fast_coder",
                    "priority": 75,
                    "requires_merge": True,
                    "payload": {"prompt": "batch item 1"},
                }
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(SystemExit) as bf_exc:
        alos_cli_main(["--home", str(home), "--mock", "enqueue", "--file", str(batch_file)])
    assert bf_exc.value.code == 0
    _ = capsys.readouterr()

    # BUG-006: duplicate `--id` returns exit code 2 with JSON error instead of raw traceback
    with pytest.raises(SystemExit) as dup_exc:
        alos_cli_main(
            ["--home", str(home), "--mock", "enqueue", "--id", "b-1", "--prompt", "duplicate"]
        )
    assert dup_exc.value.code == 2
    dup_out = json.loads(capsys.readouterr().out.strip())
    assert dup_out["error"] == "duplicate_job_id"

    with pytest.raises(SystemExit) as j_exc:
        alos_cli_main(["--home", str(home), "--mock", "jobs", "--state", "queued"])
    assert j_exc.value.code == 0
    jobs_list = json.loads(capsys.readouterr().out.strip())
    assert len(jobs_list) == 1 and jobs_list[0]["job_id"] == "b-1"

    # BUG-001: ensure_tier exception marks job failed instead of crashing daemon or orphaning lease
    loop = _build_default_stack(db_url, mock_mode=True)
    loop.queue.enqueue(
        "bad-tier-1",
        "alos",
        "probe",
        "nonexistent_tier",
        priority=99,
        payload={"prompt": "x"},
    )
    tick = loop.run_once(mock_prompt_executor)
    assert tick.outcome == "failed"
    assert tick.job_id == "bad-tier-1"
