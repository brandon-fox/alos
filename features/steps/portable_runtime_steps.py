"""Behave step definitions for portable_runtime.feature (@mocked and @live)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from behave import given, then, when

from alos.runtime import (
    RuntimePaths,
    SingleInstanceLock,
    allocate_free_port,
    bootstrap_home,
    run_doctor,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _run_unified_cli(
    home: Path, args_str: str, mock: bool = True
) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, "-m", "alos.cli", "--home", str(home)]
    if mock:
        cmd.append("--mock")
    cmd.extend(args_str.split())
    env = dict(os.environ, ALOS_HOME=str(home))
    env["ALOS_SWARM_MODE"] = "mock" if mock else "live"
    # Fixed argument list invoking alos.cli via current Python interpreter without shell.
    return subprocess.run(  # noqa: S603
        cmd,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
        env=env,
    )


@given("an empty portable ALOS_HOME directory")
def step_given_empty_home(context: Any) -> None:
    context.portable_home = context.tmp_dir / "portable_home"


@given("a bootstrapped portable ALOS_HOME directory")
def step_given_bootstrapped_home(context: Any) -> None:
    context.portable_home = context.tmp_dir / "portable_home"
    bootstrap_home(home=context.portable_home)


@when('I run the unified alos CLI in mocked mode with "{args_str}"')
def step_when_run_unified_mock(context: Any, args_str: str) -> None:
    context.u_res = _run_unified_cli(context.portable_home, args_str, mock=True)


@then("ALOS_HOME contains seeded vault templates, alos.env, and an initialized SQLite database")
def step_then_bootstrapped_files(context: Any) -> None:
    assert context.u_res.returncode == 0, context.u_res.stderr
    paths = RuntimePaths.resolve(context.portable_home)
    assert (paths.vault_dir / "USER_PROFILE.md").exists()
    assert (paths.vault_dir / "PREFERENCES.md").exists()
    assert (paths.vault_dir / "CORRECTION_LEDGER.md").exists()
    assert paths.env_file.exists()
    assert paths.sqlite_db_path.exists()


@when('I customize USER_PROFILE.md inside ALOS_HOME and re-run "bootstrap"')
def step_when_customize_and_rebootstrap(context: Any) -> None:
    profile = context.portable_home / "vault" / "USER_PROFILE.md"
    profile.write_text("# My Custom Vault\n", encoding="utf-8")
    context.u_res = _run_unified_cli(context.portable_home, "bootstrap", mock=True)


@then("USER_PROFILE.md retains my customization with zero overwritten files")
def step_then_retained_custom_profile(context: Any) -> None:
    assert context.u_res.returncode == 0
    payload = json.loads(context.u_res.stdout.strip())
    assert payload["seeded_vault_files"] == []
    profile = context.portable_home / "vault" / "USER_PROFILE.md"
    assert profile.read_text(encoding="utf-8") == "# My Custom Vault\n"


@when("an active SingleInstanceLock is held on ALOS_HOME")
def step_when_hold_active_lock(context: Any) -> None:
    paths = RuntimePaths.resolve(context.portable_home)
    lock = SingleInstanceLock(paths.lock_file)
    lock.acquire()
    context.held_lock = lock


@then('the unified CLI exits with code {code:d} and reports event "{event_name}"')
def step_then_cli_locked_code(context: Any, code: int, event_name: str) -> None:
    try:
        assert context.u_res.returncode == code, context.u_res.stdout + context.u_res.stderr
        data = json.loads(context.u_res.stdout.strip().splitlines()[-1])
        assert data["event"] == event_name
    finally:
        if getattr(context, "held_lock", None) is not None:
            context.held_lock.release()
            context.held_lock = None


@when("the active lock is replaced by a stale dead-PID lockfile")
def step_when_write_stale_lock(context: Any) -> None:
    paths = RuntimePaths.resolve(context.portable_home)
    paths.lock_file.parent.mkdir(parents=True, exist_ok=True)
    paths.lock_file.write_text(json.dumps({"pid": 99_999_999}), encoding="utf-8")


@then("the unified CLI exits with code 0 and reclaims the stale lock cleanly")
def step_then_reclaimed_stale_lock(context: Any) -> None:
    assert context.u_res.returncode == 0, context.u_res.stderr
    paths = RuntimePaths.resolve(context.portable_home)
    assert not paths.lock_file.exists()


@then('ALOS_HOME health.json exists with status "{expected_status}"')
def step_then_health_status(context: Any, expected_status: str) -> None:
    assert context.u_res.returncode == 0, context.u_res.stderr
    paths = RuntimePaths.resolve(context.portable_home)
    assert paths.health_file.exists()
    health = json.loads(paths.health_file.read_text(encoding="utf-8"))
    assert health["status"] == expected_status


@then("the ledger JSON output contains at least {min_rows:d} entry")
def step_then_ledger_json_count(context: Any, min_rows: int) -> None:
    assert context.u_res.returncode == 0, context.u_res.stderr
    rows = json.loads(context.u_res.stdout.strip())
    assert len(rows) >= min_rows


@then("the doctor JSON reports healthy true with exit code 0")
def step_then_doctor_healthy(context: Any) -> None:
    assert context.u_res.returncode == 0, context.u_res.stderr
    doc = json.loads(context.u_res.stdout.strip())
    assert doc["healthy"] is True


@when("run_doctor is invoked requiring an unreachable Ollama port")
def step_when_doctor_unreachable(context: Any) -> None:
    context.offline_doc = run_doctor(
        home=context.portable_home,
        ollama_host=f"http://127.0.0.1:{allocate_free_port()}",
        require_ollama=True,
        mock=False,
    )


@then("the doctor report marks healthy false")
def step_then_doctor_unhealthy(context: Any) -> None:
    assert context.offline_doc["healthy"] is False


@given("a built ALOS wheel installed into an isolated external runtime prefix")
def step_given_installed_wheel(context: Any) -> None:
    wheel_dir = context.tmp_dir / "wheels"
    ext_venv = context.tmp_dir / "ext_venv"
    ext_cwd = context.tmp_dir / "external_workdir"
    ext_home = context.tmp_dir / "external_alos_home"
    wheel_dir.mkdir(parents=True, exist_ok=True)
    ext_cwd.mkdir(parents=True, exist_ok=True)

    uv_bin = shutil.which("uv")
    assert uv_bin is not None, "uv executable not found in PATH"
    # Build wheel using resolved uv executable without shell.
    build_res = subprocess.run(  # noqa: S603
        [uv_bin, "build", "--wheel", "--out-dir", str(wheel_dir)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert build_res.returncode == 0, f"uv build failed: {build_res.stderr}"
    wheels = list(wheel_dir.glob("alos-*.whl"))
    assert wheels, "No wheel produced by uv build"

    # Create isolated external venv and install built wheel + cached dependencies via uv
    ext_py = ext_venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    scripts_dir = ext_py.parent
    # Provision external venv via resolved uv executable without shell.
    venv_res = subprocess.run(  # noqa: S603
        [uv_bin, "venv", str(ext_venv), "--python", sys.executable],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert venv_res.returncode == 0, f"uv venv failed: {venv_res.stderr}"
    # Install built wheel and runtime dependencies from local uv cache without shell.
    inst_res = subprocess.run(  # noqa: S603
        [
            uv_bin,
            "pip",
            "install",
            "--python",
            str(ext_py),
            str(wheels[0]),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert inst_res.returncode == 0, f"Wheel install failed: {inst_res.stderr}"

    alos_bin = scripts_dir / ("alos.exe" if os.name == "nt" else "alos")
    assert alos_bin.exists(), f"Expected installed console script at {alos_bin}"
    context.alos_bin = alos_bin
    context.ext_cwd = ext_cwd
    context.ext_home = ext_home


def _run_installed_bin(context: Any, args: list[str]) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, ALOS_HOME=str(context.ext_home))
    env.pop("ALOS_SWARM_MODE", None)
    env.pop("ALOS_QUEUE_DB_URL", None)
    # Fixed path to freshly installed wheel entrypoint inside context.tmp_dir.
    return subprocess.run(  # noqa: S603
        [str(context.alos_bin), "--home", str(context.ext_home), *args],
        cwd=str(context.ext_cwd),
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
        env=env,
    )


@when(
    'the installed alos binary runs "bootstrap" and '
    '"doctor --json --require-ollama" from an external working directory'
)
def step_when_installed_bootstrap_and_doctor(context: Any) -> None:
    context.bin_boot = _run_installed_bin(context, ["bootstrap"])
    context.bin_doc = _run_installed_bin(context, ["doctor", "--json", "--require-ollama"])


@then("both installed binary commands exit 0 with healthy live GPU and Ollama checks")
def step_then_installed_healthy(context: Any) -> None:
    assert context.bin_boot.returncode == 0, context.bin_boot.stderr
    assert context.bin_doc.returncode == 0, context.bin_doc.stderr
    doc = json.loads(context.bin_doc.stdout.strip())
    assert doc["healthy"] is True
    assert doc["checks"]["ollama"]["ok"] is True


@when(
    'the installed alos binary enqueues job "{job_id}" and runs "tick" '
    "from the external working directory"
)
def step_when_installed_enqueue_and_tick(context: Any, job_id: str) -> None:
    enq = _run_installed_bin(
        context,
        ["enqueue", "--id", job_id, "--tier", "fast_coder", "--prompt", "Reply_PORTABLE"],
    )
    assert enq.returncode == 0, enq.stderr
    context.bin_tick = _run_installed_bin(context, ["tick"])


@then(
    'the installed binary completes "{job_id}" against live Ollama '
    "using only the external ALOS_HOME"
)
def step_then_installed_completed(context: Any, job_id: str) -> None:
    assert context.bin_tick.returncode == 0, context.bin_tick.stderr
    payload = json.loads(context.bin_tick.stdout.strip())
    assert payload["outcome"] == "completed"
    assert payload["job_id"] == job_id
    assert (context.ext_home / "queue" / "compute_queue.db").exists()


@given('docker compose configuration with profile "alos" validates cleanly')
def step_given_compose_config_valid(context: Any) -> None:
    docker_bin = shutil.which("docker")
    assert docker_bin is not None
    # Validate Compose YAML via resolved docker CLI without shell.
    res = subprocess.run(  # noqa: S603
        [docker_bin, "compose", "--profile", "alos", "config", "--quiet"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert res.returncode == 0, f"docker compose config failed: {res.stderr}"


@when('the production Dockerfile is built as image "{tag}"')
def step_when_build_prod_image(context: Any, tag: str) -> None:
    docker_bin = shutil.which("docker")
    assert docker_bin is not None
    context.prod_image_tag = tag
    # Build production Dockerfile image via resolved docker CLI without shell.
    res = subprocess.run(  # noqa: S603
        [docker_bin, "build", "-f", "Dockerfile", "-t", tag, "."],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=240,
        check=False,
    )
    assert res.returncode == 0, f"docker build failed:\n{res.stderr}"


@then('the container image runs as non-root UID "{expected_uid}"')
def step_then_container_non_root(context: Any, expected_uid: str) -> None:
    docker_bin = shutil.which("docker")
    assert docker_bin is not None
    # Inspect container user ID via resolved docker CLI without shell.
    res = subprocess.run(  # noqa: S603
        [docker_bin, "run", "--rm", "--entrypoint", "id", context.prod_image_tag, "-u"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == expected_uid


@then(
    'running "bootstrap", "doctor --json", and mocked '
    '"daemon --max-ticks 1 --poll-s 0.02" inside the container all exit 0'
)
def step_then_container_commands_succeed(context: Any) -> None:
    docker_bin = shutil.which("docker")
    assert docker_bin is not None
    shell_cmd = (
        "alos bootstrap && alos doctor --json && alos --mock daemon --max-ticks 1 --poll-s 0.02"
    )
    # Run container smoke commands via resolved docker CLI without host shell.
    res = subprocess.run(  # noqa: S603
        [
            docker_bin,
            "run",
            "--rm",
            "--entrypoint",
            "sh",
            context.prod_image_tag,
            "-c",
            shell_cmd,
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert res.returncode == 0, f"Container runtime failed:\n{res.stdout}\n{res.stderr}"
    assert '"healthy": true' in res.stdout.lower()
    assert '"daemon_stopped"' in res.stdout
