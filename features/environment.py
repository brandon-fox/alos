"""Behave test environment for mocked and live local compute governor & runtime suites.

Spec: specs/035-parallel-testing-and-qa-matrix/spec.md (FR-001, FR-003, FR-009)
"""

from __future__ import annotations

import os
import shutil
import subprocess  # nosec B404
import sys
import tempfile
from pathlib import Path
from typing import Any

from alos.logs.telemetry import global_tracer
from alos.swarm.dispatcher import Ollama

_ENV_KEYS = (
    "ALOS_HOME",
    "ALOS_AUDIT_LOG_PATH",
    "ALOS_DECISION_LOG_PATH",
    "ALOS_WORKFLOWS_DIR",
    "ALOS_QUEUE_DB_URL",
    "ALOS_MOCK_SENSOR_JSON",
    "ALOS_SWARM_MODE",
)


def _live_ollama_ready() -> tuple[bool, str]:
    """Check whether local Ollama has ``qwen2.5-coder:7b-instruct`` installed for @live runs."""
    try:
        tags = Ollama("http://127.0.0.1:11434").call("/api/tags", timeout=1.5)
        installed = {str(m.get("name", "")) for m in tags.get("models", [])}
    except (OSError, ValueError) as exc:
        return False, f"local Ollama not reachable on 127.0.0.1:11434 ({exc})"
    target = "qwen2.5-coder:7b-instruct"
    if target not in installed:
        return False, f"required live test model {target!r} not installed"
    return True, ""


def _live_docker_ready() -> tuple[bool, str]:
    """Check whether the Docker daemon is reachable for @docker_live container scenarios."""
    docker_bin = shutil.which("docker")
    if docker_bin is None:
        return False, "docker CLI not installed"
    try:
        # Fixed command checking local Docker Engine daemon readiness without shell.
        res = subprocess.run(  # noqa: S603  # nosec B603
            [docker_bin, "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        if res.returncode != 0:
            return False, f"docker daemon unavailable: {res.stderr.strip()}"
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"docker probe failed: {exc}"
    return True, ""


def _skip_or_fail_live(context: Any, scenario: Any, reason: str) -> None:
    require_live = bool(context.config.userdata.get("require_live", "")) or (
        os.environ.get("ALOS_REQUIRE_LIVE") == "1"
    )
    if require_live:
        raise RuntimeError(f"Required live capability unavailable: {reason}")
    scenario.skip(reason)


def before_scenario(context: Any, scenario: Any) -> None:
    """Provision an isolated ALOS_HOME & temp directory per scenario and gate @live/OS tags."""
    context._saved_env = {k: os.environ.get(k) for k in _ENV_KEYS}
    context.tmp_dir = Path(tempfile.mkdtemp(prefix=f"alos_behave_{os.getpid()}_"))
    iso_home = context.tmp_dir / "_alos_home"
    (iso_home / "logs").mkdir(parents=True, exist_ok=True)
    os.environ["ALOS_HOME"] = str(iso_home)
    os.environ["ALOS_AUDIT_LOG_PATH"] = str(iso_home / "logs" / "system_audit.jsonl")
    os.environ["ALOS_DECISION_LOG_PATH"] = str(iso_home / "logs" / "decision_log.jsonl")
    os.environ["ALOS_WORKFLOWS_DIR"] = str(iso_home / "workflows")
    os.environ.pop("ALOS_QUEUE_DB_URL", None)
    os.environ.pop("ALOS_MOCK_SENSOR_JSON", None)
    os.environ.pop("ALOS_SWARM_MODE", None)
    global_tracer.clear()

    context.live_spinners = []
    context.child_procs = []
    tags = set(scenario.effective_tags)

    if "windows_only" in tags and sys.platform != "win32":
        scenario.skip("Skipping @windows_only scenario on non-Windows host")
        return
    if "linux_only" in tags and not sys.platform.startswith("linux"):
        scenario.skip("Skipping @linux_only scenario on non-Linux host")
        return
    if "docker_live" in tags:
        ok, why = _live_docker_ready()
        if not ok:
            _skip_or_fail_live(context, scenario, f"Skipping @docker_live scenario: {why}")
            return
    if "live" in tags and "docker_only" not in tags:
        ready, why = _live_ollama_ready()
        if not ready:
            _skip_or_fail_live(context, scenario, f"Skipping @live scenario: {why}")


def after_scenario(context: Any, _scenario: Any) -> None:
    """Guarantee all live spinners, child processes, env vars, and temp files are cleaned up."""
    for spinner in getattr(context, "live_spinners", []):
        spinner.evict_all()
    for proc in getattr(context, "child_procs", []):
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
    saved = getattr(context, "_saved_env", {})
    for key, val in saved.items():
        if val is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = val
    global_tracer.clear()
    tmp_dir = getattr(context, "tmp_dir", None)
    if tmp_dir is not None:
        shutil.rmtree(tmp_dir, ignore_errors=True)
