"""Unit and fault-injection tests for Preemptible Host Governor & ModelSpinner (Spec 032).

Covers T1 (Game launch / foreign VRAM preemption), T2 (Orphaned/hung runner tree kill),
T3 (Schmitt-trigger thermal hysteresis & anti-thrash), warm linger expiry, and live NVML probe.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

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
from alos.swarm.sensors import (
    FaultOverlaySensor,
    ScriptedSensor,
    SensorProvider,
    TelemetrySnapshot,
    WindowsNativeSensor,
    read_cpu_temp_file,
)


class ManualClock:
    """Deterministic monotonic clock for testing dwell and linger windows without sleeping."""

    def __init__(self, start: float = 1000.0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


class FakeSpinner(ModelSpinner):
    """Test spinner tracking evictions without launching an external binary."""

    def __init__(self) -> None:
        super().__init__(port=11439)
        self.evict_calls = 0
        self._fake_tier: str | None = "fast_coder"

    @property
    def active_tier(self) -> str | None:
        return self._fake_tier

    def evict_all(self, sensor: SensorProvider | None = None) -> EvictionReport:
        self.evict_calls += 1
        self._fake_tier = None
        return EvictionReport(
            elapsed_s=0.05, graceful_unloaded=True, tree_killed=True, remaining_managed_vram_mb=0
        )


def test_t1_game_launch_and_foreign_vram_preemption_and_recovery() -> None:
    """T1: Fullscreen game or foreign VRAM spike immediately preempts, pauses, and evicts."""
    clock = ManualClock()
    sensor = ScriptedSensor()
    spinner = FakeSpinner()
    docker_cmds: list[list[str]] = []

    def record_docker(cmd: list[str]) -> int:
        docker_cmds.append(cmd)
        return 0

    pauser = ContainerPauser(runner=record_docker)
    pauser.register("devcontainer-alos")

    gov = HostGovernor(
        sensor=sensor,
        spinner=spinner,
        pauser=pauser,
        clock=clock,
        state=GovernorState.WARM_ACTIVE,
    )

    # Inject foreign VRAM spike (e.g. launching a Vulkan/DX12 title allocating 5.2 GB VRAM)
    sensor.update(used_vram_mb=10200, managed_vram_mb=5000, user_idle_seconds=2.0)
    assert sensor.sample().foreign_vram_mb == 5200

    tr = gov.evaluate(has_queued_work=True)
    assert tr.state == GovernorState.USER_PREEMPTED
    assert not tr.can_pull_work
    assert gov.cancel_event.is_set()
    assert spinner.evict_calls == 1
    assert docker_cmds == [["docker", "pause", "devcontainer-alos"]]

    # Game exits and VRAM drops, but user is still moving mouse (idle=45s < 300s): stay preempted
    sensor.update(used_vram_mb=1800, managed_vram_mb=0, user_idle_seconds=45.0)
    tr_wait = gov.evaluate(has_queued_work=True)
    assert tr_wait.state == GovernorState.USER_PREEMPTED
    assert spinner.evict_calls == 1

    # User goes AFK past 300s recovery threshold: gate reopens and unpauses devcontainer
    sensor.update(user_idle_seconds=310.0)
    tr_open = gov.evaluate(has_queued_work=True)
    assert tr_open.state == GovernorState.ARMED_IDLE
    assert tr_open.can_pull_work
    assert not gov.cancel_event.is_set()
    assert docker_cmds[-1] == ["docker", "unpause", "devcontainer-alos"]


def test_t2_hung_runner_process_tree_killed_on_eviction() -> None:
    """T2: If Ollama's HTTP unload fails/hangs, ModelSpinner kills the OS process tree."""
    dummy_proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        spinner = ModelSpinner(
            port=11499,
            stock_host="http://127.0.0.1:11498",
            tiers={"fast_coder": ModelTierSpec(tier="fast_coder", model="dummy:7b")},
            evict_grace_s=0.3,
        )
        spinner._proc = dummy_proc
        spinner._active_spec = spinner.tiers["fast_coder"]
        assert spinner.server_pid == dummy_proc.pid

        sensor = ScriptedSensor(TelemetrySnapshot(used_vram_mb=1500, managed_vram_mb=0))
        report = spinner.evict_all(sensor=sensor)
        assert report.tree_killed is True
        assert report.elapsed_s < 2.0
        assert dummy_proc.poll() is not None
        assert spinner.active_tier is None
    finally:
        if dummy_proc.poll() is None:
            dummy_proc.kill()
            dummy_proc.wait(timeout=5)


def test_t3_thermal_hysteresis_prevents_bounce_and_warm_linger_evicts() -> None:
    """T3: Schmitt-trigger thermal ramp throttles, cuts off, ignores bounce, and recovers."""
    clock = ManualClock()
    sensor = ScriptedSensor()
    spinner = FakeSpinner()
    cfg = HysteresisConfig(cooling_dwell_s=180.0, throttle_dwell_s=120.0, warm_linger_s=600.0)
    gov = HostGovernor(sensor=sensor, spinner=spinner, config=cfg, clock=clock)

    # 1. Start active work
    assert gov.evaluate(has_queued_work=True).state == GovernorState.WARM_ACTIVE

    # 2. Queue drains -> enters WARM_LINGER without evicting model
    assert gov.evaluate(has_queued_work=False).state == GovernorState.WARM_LINGER
    assert spinner.evict_calls == 0

    # 3. Job arrives 90s later -> returns to WARM_ACTIVE with hot model
    clock.advance(90.0)
    assert gov.evaluate(has_queued_work=True).state == GovernorState.WARM_ACTIVE

    # 4. VRAM hits 90C -> THROTTLED
    sensor.update(vram_temp_c=90.0)
    assert gov.evaluate(has_queued_work=True).state == GovernorState.THROTTLED

    # 5. CPU spikes to 93C -> COOLING_CUTOFF + immediate VRAM eviction
    sensor.update(cpu_temp_c=93.0)
    cutoff = gov.evaluate(has_queued_work=True)
    assert cutoff.state == GovernorState.COOLING_CUTOFF
    assert spinner.evict_calls == 1

    # 6. Cools partway (GPU 64C, VRAM 80C, CPU 70C) -> MUST stay in COOLING_CUTOFF (no bounce)
    clock.advance(60.0)
    sensor.update(gpu_temp_c=64.0, vram_temp_c=80.0, cpu_temp_c=70.0)
    assert gov.evaluate(has_queued_work=True).state == GovernorState.COOLING_CUTOFF

    # 7. Drops below recovery floor (GPU 54C, VRAM 68C, CPU 55C) -> requires 180s dwell
    sensor.update(gpu_temp_c=54.0, vram_temp_c=68.0, cpu_temp_c=55.0)
    assert gov.evaluate(has_queued_work=False).state == GovernorState.COOLING_CUTOFF
    clock.advance(100.0)
    assert gov.evaluate(has_queued_work=False).state == GovernorState.COOLING_CUTOFF
    clock.advance(85.0)
    assert gov.evaluate(has_queued_work=False).state == GovernorState.ARMED_IDLE


def test_warm_linger_expiry_evicts_vram_to_cold_idle() -> None:
    """Verify WARM_LINGER unloads VRAM once the 10-minute linger window expires."""
    clock = ManualClock()
    sensor = ScriptedSensor()
    spinner = FakeSpinner()
    gov = HostGovernor(sensor=sensor, spinner=spinner, clock=clock)

    assert gov.evaluate(has_queued_work=True).state == GovernorState.WARM_ACTIVE
    assert gov.evaluate(has_queued_work=False).state == GovernorState.WARM_LINGER
    clock.advance(599.0)
    assert gov.evaluate(has_queued_work=False).state == GovernorState.WARM_LINGER
    assert spinner.evict_calls == 0

    clock.advance(2.0)
    idle = gov.evaluate(has_queued_work=False)
    assert idle.state == GovernorState.ARMED_IDLE
    assert spinner.evict_calls == 1


def test_fault_overlay_and_cpu_temp_bridge_and_live_nvml(tmp_path: Path) -> None:
    """Verify FaultOverlaySensor overrides and live WindowsNativeSensor sampling."""
    temp_file = tmp_path / "cpu_temp.txt"
    temp_file.write_text("67.5\n", encoding="utf-8")
    assert read_cpu_temp_file(temp_file) == 67.5

    live = WindowsNativeSensor(ollama_hosts=(), cpu_temp_file=temp_file)
    overlay = FaultOverlaySensor(live)
    base = overlay.sample()
    assert base.cpu_temp_c == 67.5
    if live.nvml_available:
        assert base.total_vram_mb > 0
        assert base.gpu_temp_c is not None and 15.0 <= base.gpu_temp_c <= 105.0

    overlay.inject(d3d_fullscreen=True)
    assert overlay.sample().d3d_fullscreen is True
    overlay.clear()
    assert overlay.sample().d3d_fullscreen == base.d3d_fullscreen


class _StubBackoffSpinner(ModelSpinner):
    def __init__(self, initial_slots: int, max_ok_slots: int) -> None:
        super().__init__(
            port=11494,
            tiers={"fast_coder": ModelTierSpec("fast_coder", "dummy:7b", slots=initial_slots)},
        )
        self.max_ok_slots = max_ok_slots
        self.spawned_slots: list[int] = []

    def _unload_stock_server(self) -> None:
        return None

    def _needs_server_restart(self, spec: ModelTierSpec) -> bool:
        return True

    def _stop_process_tree(self) -> bool:
        return True

    def _spawn_server(self, spec: ModelTierSpec) -> Ollama:
        self.spawned_slots.append(spec.slots)
        return Ollama(self.host)

    def _warm_model(self, _client: Ollama, spec: ModelTierSpec) -> str | None:
        return "cudaMalloc failed: out of memory" if spec.slots > self.max_ok_slots else None


def test_adaptive_cuda_oom_slot_backoff_and_exhaustion() -> None:
    """Verify ModelSpinner halves slots on CUDA OOM and raises if even 1 slot OOMs."""
    spinner = _StubBackoffSpinner(initial_slots=8, max_ok_slots=2)
    spinner.ensure_tier("fast_coder")
    assert spinner.spawned_slots == [8, 4, 2]
    assert spinner.active_model == "dummy:7b"

    with pytest.raises(KeyError):
        spinner.ensure_tier("nonexistent_tier")

    doomed = _StubBackoffSpinner(initial_slots=2, max_ok_slots=0)
    with pytest.raises(RuntimeError, match="CUDA OOM even at 1 slot"):
        doomed.ensure_tier("fast_coder")


def test_blocked_process_preemption_and_container_unregister() -> None:
    """Verify named blocked_process triggers USER_PREEMPTED and unregister removes container."""
    sensor = ScriptedSensor()
    spinner = FakeSpinner()
    cmds: list[list[str]] = []

    def runner(cmd: list[str]) -> int:
        cmds.append(cmd)
        return 0

    pauser = ContainerPauser(runner=runner)
    pauser.register("c-keep")
    pauser.register("c-drop")
    pauser.unregister("c-drop")

    gov = HostGovernor(sensor=sensor, spinner=spinner, pauser=pauser)
    sensor.update(blocked_process="Cyberpunk2077.exe")
    tr = gov.evaluate(has_queued_work=True)
    assert tr.state == GovernorState.USER_PREEMPTED
    assert cmds == [["docker", "pause", "c-keep"]]
