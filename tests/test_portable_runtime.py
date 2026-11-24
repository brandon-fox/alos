"""Unit tests for portable production runtime, PID locks, health heartbeats, and unified CLI.

Spec: specs/032-portable-production-runtime/spec.md
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from alos.runtime import (
    DaemonAlreadyRunningError,
    HealthHeartbeat,
    RuntimePaths,
    SingleInstanceLock,
    bootstrap_home,
    is_pid_alive,
    run_doctor,
)


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
