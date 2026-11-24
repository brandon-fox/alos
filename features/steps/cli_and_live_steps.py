"""Behave step definitions for cli_and_live_integration.feature (@mocked and @live)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any

from behave import given, then, when
from sqlalchemy import func, select

from alos.db.models import ComputeCapacityLedgerModel, ComputeQueueJobModel
from alos.db.session import DatabaseManager
from alos.swarm.governor import GovernorState, HostGovernor, ModelSpinner
from alos.swarm.queue import ComputeRuntimeLoop, StickyEpochQueue, default_prompt_executor
from alos.swarm.sensors import FaultOverlaySensor, WindowsNativeSensor


def _run_cli_subprocess(
    db_url: str, args_str: str, mock: bool, sensor_json: dict[str, Any] | None = None
) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, "-m", "alos.swarm.queue", "--db-url", db_url]
    if mock:
        cmd.append("--mock")
    cmd.extend(args_str.split())
    env = dict(os.environ)
    env["ALOS_SWARM_MODE"] = "mock" if mock else "live"
    if sensor_json is not None:
        env["ALOS_MOCK_SENSOR_JSON"] = json.dumps(sensor_json)
    else:
        env.pop("ALOS_MOCK_SENSOR_JSON", None)
    # Fixed argument vector invoking our own module via sys.executable without a shell.
    return subprocess.run(  # noqa: S603
        cmd,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
        env=env,
    )


@given("an isolated CLI SQLite database URL")
def step_given_cli_db(context: Any) -> None:
    db_path = context.tmp_dir / "cli_integration.db"
    context.cli_db_url = f"sqlite:///{db_path}"
    context.cli_db = DatabaseManager(db_url=context.cli_db_url)
    context.cli_db.create_all_tables()


@when('I invoke the swarm queue CLI in mocked mode with "{args_str}"')
@given('I invoke the swarm queue CLI in mocked mode with "{args_str}"')
def step_when_cli_mocked(context: Any, args_str: str) -> None:
    context.cli_res = _run_cli_subprocess(context.cli_db_url, args_str, mock=True)


@when('I invoke the swarm queue CLI in mocked gaming mode with "{args_str}"')
def step_when_cli_mocked_gaming(context: Any, args_str: str) -> None:
    context.cli_res = _run_cli_subprocess(
        context.cli_db_url,
        args_str,
        mock=True,
        sensor_json={"d3d_fullscreen": True, "user_idle_seconds": 0.0},
    )


@when('I invoke the swarm queue CLI in live mode with "{args_str}"')
def step_when_cli_live(context: Any, args_str: str) -> None:
    context.cli_res = _run_cli_subprocess(context.cli_db_url, args_str, mock=False)


@then('the CLI exits 0 with zero stderr warnings and JSON state "{expected_state}"')
def step_then_cli_status_state(context: Any, expected_state: str) -> None:
    res: subprocess.CompletedProcess[str] = context.cli_res
    assert res.returncode == 0, f"CLI failed: {res.stderr}"
    assert "RuntimeWarning" not in res.stderr, f"Unexpected stderr warning: {res.stderr}"
    payload = json.loads(res.stdout.strip())
    assert payload["state"] == expected_state


@then("the CLI exits 0 with zero stderr warnings and positive total VRAM telemetry")
def step_then_cli_live_vram(context: Any) -> None:
    res: subprocess.CompletedProcess[str] = context.cli_res
    assert res.returncode == 0, f"CLI failed: {res.stderr}"
    assert "RuntimeWarning" not in res.stderr, f"Unexpected stderr warning: {res.stderr}"
    payload = json.loads(res.stdout.strip())
    assert payload["snapshot"]["total_vram_mb"] > 0


@then('the CLI exits 0 and reports job "{job_id}" in state "{expected_state}"')
def step_then_cli_enqueued(context: Any, job_id: str, expected_state: str) -> None:
    res: subprocess.CompletedProcess[str] = context.cli_res
    assert res.returncode == 0, f"CLI failed: {res.stderr}"
    payload = json.loads(res.stdout.strip())
    assert payload["job_id"] == job_id
    assert payload["state"] == expected_state


@then('the CLI exits 0 and reports outcome "{outcome}" for job "{job_id}"')
def step_then_cli_tick_outcome(context: Any, outcome: str, job_id: str) -> None:
    res: subprocess.CompletedProcess[str] = context.cli_res
    assert res.returncode == 0, f"CLI failed: {res.stderr}"
    payload = json.loads(res.stdout.strip())
    assert payload["outcome"] == outcome, f"Expected {outcome}, got {payload} (stderr={res.stderr})"
    assert payload["job_id"] == job_id


@then('the CLI exits 0 and reports outcome "{outcome}" and state "{state_name}"')
def step_then_cli_gated_outcome(context: Any, outcome: str, state_name: str) -> None:
    res: subprocess.CompletedProcess[str] = context.cli_res
    assert res.returncode == 0, f"CLI failed: {res.stderr}"
    payload = json.loads(res.stdout.strip())
    assert payload["outcome"] == outcome
    assert payload["state"] == state_name


@then('the daemon CLI emits 3 JSON events "{ev1}", "{ev2}", and "{ev3}"')
def step_then_daemon_three_events(context: Any, ev1: str, ev2: str, ev3: str) -> None:
    res: subprocess.CompletedProcess[str] = context.cli_res
    assert res.returncode == 0, f"Daemon CLI failed: {res.stderr}"
    events = [json.loads(line)["event"] for line in res.stdout.strip().splitlines() if line.strip()]
    for expected in (ev1, ev2, ev3):
        assert expected in events, f"Missing {expected!r} in daemon events {events}"


@then('the daemon CLI emits 2 JSON events "{ev1}" and "{ev2}"')
def step_then_daemon_two_events(context: Any, ev1: str, ev2: str) -> None:
    res: subprocess.CompletedProcess[str] = context.cli_res
    assert res.returncode == 0, f"Daemon CLI failed: {res.stderr}"
    events = [json.loads(line)["event"] for line in res.stdout.strip().splitlines() if line.strip()]
    for expected in (ev1, ev2):
        assert expected in events, f"Missing {expected!r} in daemon events {events}"


@then("the SQLite database records at least {min_rows:d} capacity ledger entry")
def step_then_ledger_rows(context: Any, min_rows: int) -> None:
    with context.cli_db.get_session() as session:
        count = session.scalar(select(func.count(ComputeCapacityLedgerModel.id))) or 0
        assert int(count) >= min_rows


@then('job "{job_id}" remains queued in the SQLite database')
def step_then_job_still_queued(context: Any, job_id: str) -> None:
    with context.cli_db.get_session() as session:
        row = session.get(ComputeQueueJobModel, job_id)
        assert row is not None and row.state == "queued"


@then('job "{job_id}" has a non-empty live model response in the SQLite database')
def step_then_live_response_saved(context: Any, job_id: str) -> None:
    with context.cli_db.get_session() as session:
        row = session.get(ComputeQueueJobModel, job_id)
        assert row is not None
        assert row.state == "succeeded"
        assert row.result_json is not None
        assert len(str(row.result_json.get("response", "")).strip()) > 0


@given("a live HostGovernor and ComputeRuntimeLoop on port {port:d}")
def step_given_live_governor_loop(context: Any, port: int) -> None:
    spinner = ModelSpinner(port=port)
    context.live_spinners.append(spinner)
    live_sensor = WindowsNativeSensor(
        ollama_hosts=(spinner.host,),
        managed_pids_fn=spinner.managed_pids,
    )
    overlay = FaultOverlaySensor(live_sensor)
    overlay.inject(user_idle_seconds=600.0, d3d_fullscreen=False)

    db = DatabaseManager(db_url=f"sqlite:///{context.tmp_dir / 'live_loop.db'}")
    db.create_all_tables()
    queue = StickyEpochQueue(db=db)
    gov = HostGovernor(sensor=overlay, spinner=spinner)
    context.live_spinner = spinner
    context.live_overlay = overlay
    context.live_queue = queue
    context.live_gov = gov
    context.live_loop = ComputeRuntimeLoop(governor=gov, queue=queue)


@when('two "{tier}" prompt jobs are enqueued and executed back to back')
def step_when_two_live_jobs(context: Any, tier: str) -> None:
    context.live_queue.enqueue(
        "live-ep-1", "alos", "smoke", tier, payload={"prompt": "Say OK.", "max_tokens": 8}
    )
    context.live_queue.enqueue(
        "live-ep-2", "alos", "smoke", tier, payload={"prompt": "Say DONE.", "max_tokens": 8}
    )
    t1 = context.live_loop.run_once(default_prompt_executor)
    pid1 = context.live_spinner.server_pid
    vram1 = context.live_overlay.sample().managed_vram_mb
    t2 = context.live_loop.run_once(default_prompt_executor)
    pid2 = context.live_spinner.server_pid
    context.live_epoch_stats = (t1.outcome, t2.outcome, pid1, pid2, vram1)


@given('one "{tier}" prompt job is enqueued and executed to warm VRAM')
def step_given_one_live_job_warm(context: Any, tier: str) -> None:
    context.live_queue.enqueue(
        "live-warm-1", "alos", "smoke", tier, payload={"prompt": "Say HOT.", "max_tokens": 8}
    )
    t1 = context.live_loop.run_once(default_prompt_executor)
    assert t1.outcome == "completed"


@then(
    "both live jobs complete using the same warm Ollama server PID "
    "with >= {min_vram:d} MiB managed VRAM"
)
def step_then_same_warm_pid(context: Any, min_vram: int) -> None:
    out1, out2, pid1, pid2, vram1 = context.live_epoch_stats
    assert out1 == "completed" and out2 == "completed", f"stats={context.live_epoch_stats}"
    assert pid1 is not None and pid1 == pid2, f"stats={context.live_epoch_stats}"
    assert vram1 >= min_vram, f"stats={context.live_epoch_stats}"


@when("Direct3D fullscreen gaming is injected onto the live hardware sensor")
def step_when_inject_live_d3d(context: Any) -> None:
    context.live_overlay.inject(d3d_fullscreen=True, user_idle_seconds=0.0)


@when("an {temp_c:d}C GPU core temperature spike is injected onto the live hardware sensor")
def step_when_inject_live_temp(context: Any, temp_c: int) -> None:
    context.live_overlay.inject(gpu_temp_c=float(temp_c))


@then(
    'evaluating the live governor transitions to "{expected}" and evicts VRAM in under 2.0 seconds'
)
def step_then_live_evicts_under_2s(context: Any, expected: str) -> None:
    tr = context.live_gov.evaluate(has_queued_work=True)
    assert tr.state == GovernorState(expected)
    assert tr.eviction is not None
    assert tr.eviction.elapsed_s < 2.0, f"Eviction took {tr.eviction.elapsed_s}s >= 2.0s"
    assert tr.eviction.remaining_managed_vram_mb <= 128


@then("live managed VRAM drops to 0 MiB with no running server PID")
def step_then_live_zero_vram(context: Any) -> None:
    assert context.live_spinner.server_pid is None
    assert context.live_overlay.sample().managed_vram_mb == 0


@when("GPU temperature cools partway to {temp_c:d}C and another live job is enqueued")
def step_when_live_partial_cool(context: Any, temp_c: int) -> None:
    context.live_overlay.inject(gpu_temp_c=float(temp_c))
    context.live_queue.enqueue(
        "live-blocked-2",
        "alos",
        "smoke",
        "fast_coder",
        payload={"prompt": "Blocked?", "max_tokens": 8},
    )


@then('running one live loop tick returns outcome "{expected}" without respawning Ollama')
def step_then_live_gated(context: Any, expected: str) -> None:
    tick = context.live_loop.run_once(default_prompt_executor)
    assert tick.outcome == expected
    assert context.live_spinner.server_pid is None
