"""BDD step definitions for preemptible_compute_governor.feature (Spec 031)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from pytest_bdd import given, scenarios, then, when

from alos.db.session import DatabaseManager
from alos.swarm.governor import (
    ContainerPauser,
    EvictionReport,
    GovernorState,
    HostGovernor,
    ModelSpinner,
)
from alos.swarm.queue import StickyEpochQueue
from alos.swarm.sensors import ScriptedSensor

scenarios("../features/preemptible_compute_governor.feature")


class _FakeClock:
    def __init__(self, initial: float = 100.0) -> None:
        self.now = initial

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@given('a warm local compute governor with registered container "alos-dev-1"')
def step_warm_governor(bdd_context: dict[str, Any]) -> None:
    clock = _FakeClock()
    sensor = ScriptedSensor()
    spinner = MagicMock(spec=ModelSpinner)
    spinner.active_tier = "fast_coder"

    def fake_evict(_s: object = None) -> EvictionReport:
        spinner.active_tier = None
        return EvictionReport(
            elapsed_s=0.12,
            graceful_unloaded=True,
            tree_killed=True,
            remaining_managed_vram_mb=0,
        )

    spinner.evict_all.side_effect = fake_evict
    commands: list[list[str]] = []

    def record_cmd(cmd: list[str]) -> int:
        commands.append(cmd)
        return 0

    pauser = ContainerPauser(runner=record_cmd)
    pauser.register("alos-dev-1")
    gov = HostGovernor(
        sensor=sensor,
        spinner=spinner,
        pauser=pauser,
        clock=clock,
        state=GovernorState.WARM_ACTIVE,
    )
    bdd_context.update(clock=clock, sensor=sensor, spinner=spinner, pauser=pauser, gov=gov)


@when("Direct3D fullscreen gaming activity is detected")
def step_d3d_detected(bdd_context: dict[str, Any]) -> None:
    bdd_context["sensor"].update(d3d_fullscreen=True, user_idle_seconds=0.0)
    bdd_context["transition"] = bdd_context["gov"].evaluate(has_queued_work=True)


@then('the governor state transitions to "USER_PREEMPTED"')
def step_assert_user_preempted(bdd_context: dict[str, Any]) -> None:
    assert bdd_context["gov"].state == GovernorState.USER_PREEMPTED
    assert bdd_context["gov"].cancel_event.is_set()


@then('worker container "alos-dev-1" is paused')
def step_assert_container_paused(bdd_context: dict[str, Any]) -> None:
    assert "alos-dev-1" in bdd_context["pauser"].paused_containers


@then("the active model tier is evicted from VRAM")
def step_assert_model_evicted(bdd_context: dict[str, Any]) -> None:
    assert bdd_context["spinner"].evict_all.called
    assert bdd_context["spinner"].active_tier is None


@when("GPU core temperature rises to 76C and then 83C")
def step_thermal_ramp(bdd_context: dict[str, Any]) -> None:
    sensor: ScriptedSensor = bdd_context["sensor"]
    gov: HostGovernor = bdd_context["gov"]
    sensor.update(gpu_temp_c=76.0)
    first = gov.evaluate(has_queued_work=True)
    assert first.state == GovernorState.THROTTLED
    sensor.update(gpu_temp_c=83.0)
    gov.evaluate(has_queued_work=True)


@then('the governor state transitions to "COOLING_CUTOFF"')
def step_assert_cooling_cutoff(bdd_context: dict[str, Any]) -> None:
    assert bdd_context["gov"].state == GovernorState.COOLING_CUTOFF


@when("GPU core temperature drops slightly to 78C")
def step_slight_cool(bdd_context: dict[str, Any]) -> None:
    bdd_context["clock"].advance(15.0)
    bdd_context["sensor"].update(gpu_temp_c=78.0)
    bdd_context["gov"].evaluate(has_queued_work=True)


@then('the governor state remains "COOLING_CUTOFF"')
def step_still_cooling_cutoff(bdd_context: dict[str, Any]) -> None:
    assert bdd_context["gov"].state == GovernorState.COOLING_CUTOFF


@when("GPU core temperature holds at 55C across the recovery dwell window")
def step_hold_cool_dwell(bdd_context: dict[str, Any]) -> None:
    bdd_context["sensor"].update(gpu_temp_c=55.0, vram_temp_c=64.0, cpu_temp_c=52.0)
    bdd_context["gov"].evaluate(has_queued_work=False)
    bdd_context["clock"].advance(185.0)
    bdd_context["gov"].evaluate(has_queued_work=False)


@then('the governor state recovers to "ARMED_IDLE"')
def step_recovered_armed_idle(bdd_context: dict[str, Any]) -> None:
    assert bdd_context["gov"].state == GovernorState.ARMED_IDLE
    assert not bdd_context["gov"].cancel_event.is_set()
    assert "alos-dev-1" not in bdd_context["pauser"].paused_containers


@given('a sticky epoch queue with alternating "fast_coder" and "reasoner" jobs')
def step_epoch_queue_setup(tmp_path: Path, bdd_context: dict[str, Any]) -> None:
    db = DatabaseManager(db_url=f"sqlite:///{tmp_path / 'bdd_queue.db'}")
    db.create_all_tables()
    q = StickyEpochQueue(db=db)
    q.enqueue("j1", "alos", "audit", "fast_coder", priority=50)
    q.enqueue("j2", "alos", "audit", "reasoner", priority=50)
    q.enqueue("j3", "alos", "audit", "fast_coder", priority=50)
    q.enqueue("j4", "alos", "audit", "reasoner", priority=50)
    bdd_context["queue"] = q


@when('a worker pulls jobs while "reasoner" is the active warm tier')
def step_pull_jobs_with_affinity(bdd_context: dict[str, Any]) -> None:
    q: StickyEpochQueue = bdd_context["queue"]
    order: list[str] = []
    active = "reasoner"
    for _ in range(4):
        leased = q.lease_next(active_tier=active)
        assert leased is not None
        order.append(leased.model_tier)
        active = leased.model_tier
        q.complete_job(leased.job_id)
    bdd_context["leased_tiers"] = order


@then('all "reasoner" jobs lease before any "fast_coder" job')
def step_verify_affinity_order(bdd_context: dict[str, Any]) -> None:
    assert bdd_context["leased_tiers"] == [
        "reasoner",
        "reasoner",
        "fast_coder",
        "fast_coder",
    ]
