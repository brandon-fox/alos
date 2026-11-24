"""Behave step definitions for governor_spindown.feature."""

from __future__ import annotations

import subprocess
import sys
from typing import Any

from behave import given, then, when

from alos.db.session import DatabaseManager
from alos.runtime import allocate_free_port
from alos.swarm.dispatcher import Ollama
from alos.swarm.governor import (
    ContainerPauser,
    EvictionReport,
    GovernorState,
    HostGovernor,
    HysteresisConfig,
    ModelSpinner,
    ModelTierSpec,
)
from alos.swarm.queue import ComputeRuntimeLoop, StickyEpochQueue, mock_prompt_executor
from alos.swarm.sensors import ScriptedSensor, SensorProvider, TelemetrySnapshot


class _StepClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


class _SpySpinner(ModelSpinner):
    def __init__(self, initial_tier: str | None = "fast_coder") -> None:
        super().__init__(port=allocate_free_port())
        self.evict_calls = 0
        self._tier = initial_tier

    @property
    def active_tier(self) -> str | None:
        return self._tier

    def ensure_tier(self, tier_name: str, warm_load: bool = True) -> Ollama:
        self._tier = tier_name
        return Ollama(self.host)

    def evict_all(self, sensor: SensorProvider | None = None) -> EvictionReport:
        self.evict_calls += 1
        self._tier = None
        return EvictionReport(
            elapsed_s=0.03, graceful_unloaded=True, tree_killed=True, remaining_managed_vram_mb=0
        )


class _OomBackoffSpinner(ModelSpinner):
    """Simulates CUDA OOM above ``max_working_slots`` without starting external processes."""

    def __init__(self, initial_slots: int, max_working_slots: int) -> None:
        super().__init__(
            port=allocate_free_port(),
            tiers={
                "fast_coder": ModelTierSpec(
                    tier="fast_coder", model="qwen2.5-coder:7b-instruct", slots=initial_slots
                )
            },
        )
        self.max_working_slots = max_working_slots
        self.attempted_slots: list[int] = []

    def _unload_stock_server(self) -> None:
        return None

    def _needs_server_restart(self, spec: ModelTierSpec) -> bool:
        return True

    def _stop_process_tree(self) -> bool:
        return True

    def _spawn_server(self, spec: ModelTierSpec) -> Ollama:
        self.attempted_slots.append(spec.slots)
        return Ollama(self.host)

    def _warm_model(self, _client: Ollama, spec: ModelTierSpec) -> str | None:
        return "cudaMalloc failed: out of memory" if spec.slots > self.max_working_slots else None


@given('a mocked compute governor in "{state_name}" with container "{container_name}"')
def step_given_mocked_governor(context: Any, state_name: str, container_name: str) -> None:
    clock = _StepClock()
    sensor = ScriptedSensor()
    spinner = _SpySpinner(initial_tier="fast_coder")
    docker_log: list[list[str]] = []

    def record_docker(cmd: list[str]) -> int:
        docker_log.append(cmd)
        return 0

    pauser = ContainerPauser(runner=record_docker)
    pauser.register(container_name)
    gov = HostGovernor(
        sensor=sensor,
        spinner=spinner,
        pauser=pauser,
        config=HysteresisConfig(),
        clock=clock,
        state=GovernorState(state_name),
    )
    context.clock = clock
    context.sensor = sensor
    context.spinner = spinner
    context.pauser = pauser
    context.docker_log = docker_log
    context.gov = gov


@when("host telemetry reports Direct3D fullscreen gaming")
def step_when_d3d_gaming(context: Any) -> None:
    context.sensor.update(d3d_fullscreen=True, user_idle_seconds=0.0)


@when("NVML reports WDDM sentinel process memory with {used_mb:d} MiB total used VRAM")
def step_when_wddm_sentinel(context: Any, used_mb: int) -> None:
    # WDDM sentinel filtering maps 2^64-1 per-PID values to 0 so foreign VRAM uses real used_mb.
    context.sensor.update(used_vram_mb=used_mb, managed_vram_mb=0, compute_pids=(4, 1692))


@when("host telemetry reports {used_mb:d} MiB used VRAM with {managed_mb:d} MiB managed VRAM")
def step_when_vram_values(context: Any, used_mb: int, managed_mb: int) -> None:
    context.sensor.update(used_vram_mb=used_mb, managed_vram_mb=managed_mb)


@when(
    "foreign VRAM clears to {used_mb:d} MiB and idle hits {idle_s:d}s "
    'but blocked process "{proc_name}" runs'
)
def step_when_blocked_proc(context: Any, used_mb: int, idle_s: int, proc_name: str) -> None:
    context.sensor.update(
        d3d_fullscreen=False,
        used_vram_mb=used_mb,
        managed_vram_mb=0,
        user_idle_seconds=float(idle_s),
        blocked_process=proc_name,
    )


@when("gaming stops with {used_mb:d} MiB used VRAM and {idle_s:d}s user idle")
def step_when_gaming_stops_short_idle(context: Any, used_mb: int, idle_s: int) -> None:
    context.sensor.update(
        d3d_fullscreen=False,
        blocked_process=None,
        used_vram_mb=used_mb,
        managed_vram_mb=0,
        user_idle_seconds=float(idle_s),
    )


@when("user idle reaches {idle_s:d}s with {used_mb:d} MiB used VRAM")
def step_when_idle_reaches(context: Any, idle_s: int, used_mb: int) -> None:
    context.sensor.update(
        d3d_fullscreen=False,
        blocked_process=None,
        used_vram_mb=used_mb,
        managed_vram_mb=0,
        user_idle_seconds=float(idle_s),
    )


@when('evaluating the governor with queued work transitions to "{expected}"')
@then('evaluating the governor with queued work transitions to "{expected}"')
@then('evaluating the governor with queued work stays in "{expected}"')
def step_eval_with_work(context: Any, expected: str) -> None:
    context.last_transition = context.gov.evaluate(has_queued_work=True)
    assert context.gov.state == GovernorState(expected), (
        f"Expected {expected}, got {context.gov.state} ({context.last_transition.reason})"
    )


@then('evaluating the governor without work stays in "{expected}"')
@then('evaluating the governor without work transitions to "{expected}"')
def step_eval_without_work(context: Any, expected: str) -> None:
    context.last_transition = context.gov.evaluate(has_queued_work=False)
    assert context.gov.state == GovernorState(expected), (
        f"Expected {expected}, got {context.gov.state} ({context.last_transition.reason})"
    )


@then("the cancellation event is signaled")
def step_assert_cancelled(context: Any) -> None:
    assert context.gov.cancel_event.is_set() is True


@then("the cancellation event is cleared")
def step_assert_cancel_cleared(context: Any) -> None:
    assert context.gov.cancel_event.is_set() is False


@then('container "{container_name}" is paused via docker')
def step_assert_paused(context: Any, container_name: str) -> None:
    assert container_name in context.pauser.paused_containers
    assert ["docker", "pause", container_name] in context.docker_log


@then('container "{container_name}" is unpaused via docker')
def step_assert_unpaused(context: Any, container_name: str) -> None:
    assert container_name not in context.pauser.paused_containers
    assert ["docker", "unpause", container_name] in context.docker_log


@then("the model spinner evicts VRAM once")
def step_assert_evicted_once(context: Any) -> None:
    assert context.spinner.evict_calls == 1
    assert context.spinner.active_tier is None


@given("a live dummy child process attached to a ModelSpinner on an ephemeral port")
def step_given_dummy_child(context: Any) -> None:
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    context.child_procs.append(proc)
    spinner = ModelSpinner(
        port=allocate_free_port(),
        stock_host=f"http://127.0.0.1:{allocate_free_port()}",
        tiers={"fast_coder": ModelTierSpec(tier="fast_coder", model="dummy:7b")},
        evict_grace_s=0.15,
    )
    spinner._proc = proc
    spinner._active_spec = spinner.tiers["fast_coder"]
    context.dummy_proc = proc
    context.spinner = spinner


@when("the ModelSpinner executes evict_all")
def step_when_evict_all(context: Any) -> None:
    sensor = ScriptedSensor(TelemetrySnapshot(used_vram_mb=1800, managed_vram_mb=0))
    context.eviction_report = context.spinner.evict_all(sensor=sensor)


@then("the eviction completes in under 2.0 seconds with tree_killed true")
def step_then_evict_fast(context: Any) -> None:
    rep: EvictionReport = context.eviction_report
    assert rep.elapsed_s < 2.0
    assert rep.tree_killed is True


@then("the dummy child process is terminated")
def step_then_dummy_dead(context: Any) -> None:
    assert context.dummy_proc.poll() is not None


@given(
    "a ModelSpinner configured with {init_slots:d} slots "
    "that hits CUDA OOM above {ok_slots:d} slots"
)
def step_given_oom_spinner(context: Any, init_slots: int, ok_slots: int) -> None:
    context.oom_spinner = _OomBackoffSpinner(initial_slots=init_slots, max_working_slots=ok_slots)


@when('ensure_tier is called for "{tier_name}"')
def step_when_ensure_tier(context: Any, tier_name: str) -> None:
    context.oom_spinner.ensure_tier(tier_name, warm_load=True)


@then("the spinner backs off slots from 8 to 4 to 2 and succeeds at 2 slots")
def step_then_backoff_sequence(context: Any) -> None:
    assert context.oom_spinner.attempted_slots == [8, 4, 2]
    assert context.oom_spinner._active_spec is not None
    assert context.oom_spinner._active_spec.slots == 2


@when("host temperatures reach GPU {gpu_c:d}C, VRAM {vram_c:d}C, CPU {cpu_c:d}C")
@when("temperatures drop below recovery floor to GPU {gpu_c:d}C, VRAM {vram_c:d}C, CPU {cpu_c:d}C")
def step_when_temps(context: Any, gpu_c: int, vram_c: int, cpu_c: int) -> None:
    context.sensor.update(
        gpu_temp_c=float(gpu_c), vram_temp_c=float(vram_c), cpu_temp_c=float(cpu_c)
    )


@when(
    "clock advances {sec:d}s and temperatures cool partway to "
    "GPU {gpu_c:d}C, VRAM {vram_c:d}C, CPU {cpu_c:d}C"
)
def step_when_advance_and_partial_cool(
    context: Any, sec: int, gpu_c: int, vram_c: int, cpu_c: int
) -> None:
    context.clock.advance(float(sec))
    context.sensor.update(
        gpu_temp_c=float(gpu_c), vram_temp_c=float(vram_c), cpu_temp_c=float(cpu_c)
    )


@when("clock advances {sec:d}s and GPU briefly spikes to {spike_c:d}C then returns to {cool_c:d}C")
def step_when_mid_dwell_spike(context: Any, sec: int, spike_c: int, cool_c: int) -> None:
    context.clock.advance(float(sec))
    context.sensor.update(gpu_temp_c=float(spike_c))
    context.gov.evaluate(has_queued_work=False)
    context.sensor.update(gpu_temp_c=float(cool_c))


@then("evaluating the governor without work resets the recovery dwell timer")
def step_then_dwell_reset(context: Any) -> None:
    context.gov.evaluate(has_queued_work=False)
    assert context.gov.state == GovernorState.COOLING_CUTOFF
    # Advancing only 100s more (total < 180s since reset) must still stay in COOLING_CUTOFF
    context.clock.advance(100.0)
    assert context.gov.evaluate(has_queued_work=False).state == GovernorState.COOLING_CUTOFF


@when("clock advances {sec:d}s at GPU {gpu_c:d}C, VRAM {vram_c:d}C, CPU {cpu_c:d}C")
def step_when_advance_at_cool(context: Any, sec: int, gpu_c: int, vram_c: int, cpu_c: int) -> None:
    context.sensor.update(
        gpu_temp_c=float(gpu_c), vram_temp_c=float(vram_c), cpu_temp_c=float(cpu_c)
    )
    context.clock.advance(float(sec))


@given('a mocked runtime loop with active tier "{tier_name}"')
def step_given_mocked_loop(context: Any, tier_name: str) -> None:
    clock = _StepClock()
    sensor = ScriptedSensor()
    spinner = _SpySpinner(initial_tier=tier_name)
    gov = HostGovernor(sensor=sensor, spinner=spinner, clock=clock, state=GovernorState.WARM_ACTIVE)
    db = DatabaseManager(db_url=f"sqlite:///{context.tmp_dir / 'throttled_loop.db'}")
    db.create_all_tables()
    queue = StickyEpochQueue(db=db)
    context.clock = clock
    context.sensor = sensor
    context.spinner = spinner
    context.gov = gov
    context.queue = queue
    context.loop = ComputeRuntimeLoop(governor=gov, queue=queue)


@when("host telemetry enters light desktop input throttle with {idle_s:d}s idle")
def step_when_light_desk_throttle(context: Any, idle_s: int) -> None:
    context.sensor.update(user_idle_seconds=float(idle_s))


@when('a "{tier_name}" job is enqueued while "reasoner" is warm')
def step_when_enqueue_for_throttle_check(context: Any, tier_name: str) -> None:
    idx = getattr(context, "enq_idx", 0) + 1
    context.enq_idx = idx
    context.queue.enqueue(f"tjob-{idx}", "alos", "check", tier_name, payload={"prompt": "hi"})


@then('running one loop tick returns outcome "{expected}" without swapping tiers')
def step_then_throttled_wait(context: Any, expected: str) -> None:
    res = context.loop.run_once(mock_prompt_executor)
    assert res.outcome == expected
    assert context.spinner.active_tier == "reasoner"


@then('running one loop tick returns outcome "{expected}" on "{expected_tier}"')
def step_then_completed_on_tier(context: Any, expected: str, expected_tier: str) -> None:
    res = context.loop.run_once(mock_prompt_executor)
    assert res.outcome == expected
    assert res.active_tier == expected_tier


@when("user idle returns to {idle_s:d}s and clock advances {advance_s:d}s with an empty queue")
def step_when_drain_to_linger_expiry(context: Any, idle_s: int, advance_s: int) -> None:
    # Drain remaining queued work, then advance past throttle recovery and linger timeout.
    context.sensor.update(user_idle_seconds=float(idle_s))
    context.gov.evaluate(has_queued_work=True)
    context.clock.advance(130.0)
    while context.queue.has_runnable_work():
        leased = context.queue.lease_next()
        if leased:
            context.queue.complete_job(leased.job_id)
    context.gov.evaluate(has_queued_work=False)
    context.clock.advance(float(advance_s))


@then('evaluating the governor without work evicts VRAM and transitions to "{expected}"')
def step_then_linger_evicts(context: Any, expected: str) -> None:
    prev_evicts = context.spinner.evict_calls
    tr = context.gov.evaluate(has_queued_work=False)
    assert tr.state == GovernorState(expected)
    assert context.spinner.evict_calls == prev_evicts + 1
