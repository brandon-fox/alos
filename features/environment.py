"""Behave test environment for mocked and live local compute governor & runtime suites."""

from __future__ import annotations

import shutil
import subprocess  # nosec B404
import tempfile
from pathlib import Path
from typing import Any

from alos.swarm.dispatcher import Ollama


def _live_ollama_ready() -> tuple[bool, str]:
    """Check whether local Ollama has ``qwen2.5-coder:7b-instruct`` installed for @live runs."""
    try:
        tags = Ollama("http://127.0.0.1:11434").call("/api/tags", timeout=2.0)
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


def before_scenario(context: Any, scenario: Any) -> None:
    """Provision an isolated temporary directory per scenario and gate @live when offline."""
    context.tmp_dir = Path(tempfile.mkdtemp(prefix="alos_behave_"))
    context.live_spinners = []
    context.child_procs = []
    tags = set(scenario.effective_tags)
    if "docker_live" in tags:
        ok, why = _live_docker_ready()
        if not ok:
            scenario.skip(f"Skipping @docker_live scenario: {why}")
            return
    if "live" in tags and "docker_only" not in tags:
        ready, why = _live_ollama_ready()
        if not ready:
            scenario.skip(f"Skipping @live scenario: {why}")


def after_scenario(context: Any, _scenario: Any) -> None:
    """Guarantee all live spinners, child processes, and temp files are cleaned up."""
    for spinner in getattr(context, "live_spinners", []):
        spinner.evict_all()
    for proc in getattr(context, "child_procs", []):
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
    tmp_dir = getattr(context, "tmp_dir", None)
    if tmp_dir is not None:
        shutil.rmtree(tmp_dir, ignore_errors=True)
