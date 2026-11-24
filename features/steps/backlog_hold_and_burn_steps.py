"""Behave step definitions for backlog_hold_and_burn.feature (@mocked)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from behave import given, then, when

from alos.runtime import RuntimePaths, bootstrap_home


def _run_spec037_cli(home: Path, args_str: str) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, "-m", "alos.cli", "--home", str(home), "--mock", *args_str.split()]
    env = dict(os.environ)
    env["ALOS_SWARM_MODE"] = "mock"
    env["ALOS_MOCK_SENSOR_JSON"] = json.dumps({"user_idle_seconds": 15.0, "d3d_fullscreen": False})
    # Fixed argument vector invoking our own CLI module via sys.executable without a shell.
    return subprocess.run(  # noqa: S603
        cmd, capture_output=True, text=True, timeout=60, check=False, env=env
    )


@given("an isolated Spec 037 ALOS_HOME")
def step_given_spec037_home(context: Any) -> None:
    context.s37_home = context.tmp_dir / "s37_home"
    bootstrap_home(home=context.s37_home)


@when('I run the Spec 037 queue CLI in active-user mode with "{args_str}"')
def step_when_spec037_cli(context: Any, args_str: str) -> None:
    context.s37_res = _run_spec037_cli(context.s37_home, args_str)


@then('the Spec 037 CLI reports outcome "{expected_outcome}"')
def step_then_spec037_outcome(context: Any, expected_outcome: str) -> None:
    res: subprocess.CompletedProcess[str] = context.s37_res
    assert res.returncode == 0, f"CLI failed: {res.stderr}"
    payload = json.loads(res.stdout.strip())
    assert payload["outcome"] == expected_outcome


@then("the Spec 037 burn report shows 1 completed job and creates the Markdown deliverable")
def step_then_spec037_burn_report(context: Any) -> None:
    res: subprocess.CompletedProcess[str] = context.s37_res
    assert res.returncode == 0, f"CLI failed: {res.stderr}"
    payload = json.loads(res.stdout.strip())
    assert payload["completed"] == 1
    paths = RuntimePaths.resolve(context.s37_home)
    assert (paths.results_dir / "brandon-fox__alos" / "bdd-burn-1.md").exists()
    assert (paths.results_dir / "burn_digest.md").exists()


@then('the Spec 037 review report updates 1 job to "{expected_state}"')
def step_then_spec037_review(context: Any, expected_state: str) -> None:
    res: subprocess.CompletedProcess[str] = context.s37_res
    assert res.returncode == 0, f"CLI failed: {res.stderr}"
    payload = json.loads(res.stdout.strip())
    assert payload["updated"] == 1
    assert payload["target_state"] == expected_state


@then("the Spec 037 backlog stage report stages at least 25 jobs across 4 repositories")
def step_then_spec037_backlog_staged(context: Any) -> None:
    res: subprocess.CompletedProcess[str] = context.s37_res
    assert res.returncode == 0, f"CLI failed: {res.stderr}"
    payload = json.loads(res.stdout.strip())
    assert payload["staged_new"] >= 25
    assert len(payload["by_repo"]) == 4
    assert payload["estimated_minutes"] >= 120.0
