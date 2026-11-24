"""Hardware and user-activity telemetry sensors for the Preemptible Compute Governor.

Spec: specs/032-preemptible-compute-governor/spec.md (FR-001, FR-010)
ADR: docs/adr/0015-adopt-preemptible-host-governor-and-sticky-model-epoch-queue.md

On Windows, polls NVIDIA NVML (``nvml.dll``), Direct3D fullscreen/presentation notification
state (``shell32.SHQueryUserNotificationState``), and HID idle ticks
(``user32.GetLastInputInfo``) directly in-process via ``ctypes`` so background monitoring
spawns zero console subprocesses during idle hours.
"""

from __future__ import annotations

import contextlib
import ctypes
import os
import sys
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Protocol

from alos.swarm.dispatcher import Ollama

NVML_SUCCESS = 0
NVML_TEMPERATURE_GPU = 0
NVML_FI_DEV_MEMORY_TEMP = 82
QUNS_RUNNING_D3D_FULL_SCREEN = 3
QUNS_PRESENTATION_MODE = 4
BYTES_PER_MIB = 1024 * 1024


@dataclass(frozen=True)
class TelemetrySnapshot:
    """Point-in-time host thermal, VRAM, and human-activity reading."""

    gpu_temp_c: float | None = None
    vram_temp_c: float | None = None
    cpu_temp_c: float | None = None
    gpu_util_pct: int | None = None
    total_vram_mb: int = 0
    used_vram_mb: int = 0
    managed_vram_mb: int = 0
    compute_pids: tuple[int, ...] = ()
    d3d_fullscreen: bool = False
    user_idle_seconds: float = 3600.0
    blocked_process: str | None = None

    @property
    def foreign_vram_mb(self) -> int:
        """GPU memory held by programs outside our managed Ollama instance."""
        return max(0, self.used_vram_mb - self.managed_vram_mb)


class SensorProvider(Protocol):
    """Protocol implemented by live OS sensors and deterministic test doubles."""

    def sample(self) -> TelemetrySnapshot:
        """Capture one telemetry reading without blocking inference loops."""


class _NvmlUtilization(ctypes.Structure):
    _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]


class _NvmlMemory(ctypes.Structure):
    _fields_ = [
        ("total", ctypes.c_ulonglong),
        ("free", ctypes.c_ulonglong),
        ("used", ctypes.c_ulonglong),
    ]


class _NvmlProcessInfoV3(ctypes.Structure):
    _fields_ = [
        ("pid", ctypes.c_uint),
        ("usedGpuMemory", ctypes.c_ulonglong),
        ("gpuInstanceId", ctypes.c_uint),
        ("computeInstanceId", ctypes.c_uint),
    ]


class _NvmlFieldValue(ctypes.Structure):
    _fields_ = [
        ("fieldId", ctypes.c_uint),
        ("scopeId", ctypes.c_uint),
        ("timestamp", ctypes.c_longlong),
        ("latencyUsec", ctypes.c_longlong),
        ("valueType", ctypes.c_uint),
        ("nvmlReturn", ctypes.c_uint),
        ("value_ui", ctypes.c_ulonglong),
    ]


class _LastInputInfo(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def _load_nvml_library() -> Any | None:
    """Load nvml.dll on Windows or libnvidia-ml.so.1 on Linux when present."""
    candidates = (
        ("nvml.dll", r"C:\Windows\System32\nvml.dll")
        if sys.platform == "win32"
        else ("libnvidia-ml.so.1",)
    )
    loader = getattr(ctypes, "WinDLL", ctypes.CDLL) if sys.platform == "win32" else ctypes.CDLL
    for name in candidates:
        with contextlib.suppress(OSError):
            return loader(name)
    return None


class NvmlProbe:
    """In-process NVIDIA Management Library reader for GPU temps, VRAM, and compute PIDs."""

    def __init__(self, device_index: int = 0) -> None:
        self._lib = _load_nvml_library()
        self._handle = ctypes.c_void_p()
        self._ready = False
        if self._lib is not None:
            self._ready = self._initialize(device_index)

    def _initialize(self, device_index: int) -> bool:
        if self._lib is None:
            return False
        with contextlib.suppress(AttributeError, OSError):
            if self._lib.nvmlInit_v2() != NVML_SUCCESS:
                return False
            rc = self._lib.nvmlDeviceGetHandleByIndex_v2(
                ctypes.c_uint(device_index), ctypes.byref(self._handle)
            )
            return bool(rc == NVML_SUCCESS)
        return False

    @property
    def available(self) -> bool:
        """True when NVML initialized and bound to the target GPU."""
        return self._ready

    def read_gpu_temp(self) -> float | None:
        """Return GPU core temperature in Celsius."""
        if not self._ready or self._lib is None:
            return None
        temp = ctypes.c_uint(0)
        with contextlib.suppress(AttributeError, OSError):
            rc = self._lib.nvmlDeviceGetTemperature(
                self._handle, ctypes.c_uint(NVML_TEMPERATURE_GPU), ctypes.byref(temp)
            )
            if rc == NVML_SUCCESS:
                return float(temp.value)
        return None

    def read_vram_temp(self) -> float | None:
        """Return GDDR memory junction temperature in Celsius when exposed by the driver."""
        if not self._ready or self._lib is None:
            return None
        field_val = _NvmlFieldValue(fieldId=NVML_FI_DEV_MEMORY_TEMP)
        with contextlib.suppress(AttributeError, OSError):
            rc = self._lib.nvmlDeviceGetFieldValues(
                self._handle, ctypes.c_int(1), ctypes.byref(field_val)
            )
            valid = rc == NVML_SUCCESS and field_val.nvmlReturn == NVML_SUCCESS
            if valid and 0 < field_val.value_ui < 150:
                return float(field_val.value_ui)
        return None

    def read_utilization_and_memory(self) -> tuple[int | None, int, int]:
        """Return (gpu_util_pct, used_vram_mb, total_vram_mb)."""
        if not self._ready or self._lib is None:
            return None, 0, 0
        util = _NvmlUtilization()
        mem = _NvmlMemory()
        gpu_util: int | None = None
        used_mb = total_mb = 0
        with contextlib.suppress(AttributeError, OSError):
            if self._lib.nvmlDeviceGetUtilizationRates(self._handle, ctypes.byref(util)) == 0:
                gpu_util = int(util.gpu)
            if self._lib.nvmlDeviceGetMemoryInfo(self._handle, ctypes.byref(mem)) == 0:
                used_mb = int(mem.used // BYTES_PER_MIB)
                total_mb = int(mem.total // BYTES_PER_MIB)
        return gpu_util, used_mb, total_mb

    def read_compute_processes(self) -> dict[int, int]:
        """Return {pid: used_vram_mb} for active CUDA compute processes on the GPU."""
        if not self._ready or self._lib is None:
            return {}
        count = ctypes.c_uint(32)
        buf = (_NvmlProcessInfoV3 * 32)()
        fn = getattr(self._lib, "nvmlDeviceGetComputeRunningProcesses_v3", None)
        if fn is None:
            return {}
        with contextlib.suppress(OSError):
            rc = fn(self._handle, ctypes.byref(count), buf)
            if rc == NVML_SUCCESS:
                # Windows WDDM returns NVML_VALUE_NOT_AVAILABLE (~2^64-1) for per-PID VRAM.
                max_valid_bytes = 1 << 40
                return {
                    int(buf[i].pid): (
                        int(buf[i].usedGpuMemory // BYTES_PER_MIB)
                        if 0 <= int(buf[i].usedGpuMemory) < max_valid_bytes
                        else 0
                    )
                    for i in range(min(int(count.value), 32))
                }
        return {}


def query_win32_idle_seconds() -> float:
    """Return seconds elapsed since last keyboard/mouse input on Windows."""
    if sys.platform != "win32":
        return 3600.0
    user32 = getattr(ctypes, "windll", None)
    if user32 is None:
        return 3600.0
    info = _LastInputInfo(cbSize=ctypes.sizeof(_LastInputInfo))
    with contextlib.suppress(AttributeError, OSError):
        if user32.user32.GetLastInputInfo(ctypes.byref(info)):
            tick = int(user32.kernel32.GetTickCount()) & 0xFFFFFFFF
            elapsed_ms = (tick - int(info.dwTime)) & 0xFFFFFFFF
            return max(0.0, elapsed_ms / 1000.0)
    return 3600.0


def query_win32_d3d_fullscreen() -> bool:
    """Return True when Windows reports Direct3D fullscreen gaming or presentation mode."""
    if sys.platform != "win32":
        return False
    win = getattr(ctypes, "windll", None)
    if win is None:
        return False
    state = ctypes.c_int(0)
    with contextlib.suppress(AttributeError, OSError):
        if win.shell32.SHQueryUserNotificationState(ctypes.byref(state)) == 0:
            return state.value in (QUNS_RUNNING_D3D_FULL_SCREEN, QUNS_PRESENTATION_MODE)
    return False


def query_ollama_vram_mb(hosts: Sequence[str]) -> int:
    """Sum ``size_vram`` across our managed Ollama endpoints in MiB."""
    total_bytes = 0
    for host in hosts:
        if not host.startswith(("http://", "https://")):
            continue
        with contextlib.suppress(OSError, ValueError):
            models = Ollama(host.rstrip("/")).call("/api/ps", timeout=0.4).get("models", [])
            total_bytes += sum(int(m.get("size_vram", 0)) for m in models)
    return total_bytes // BYTES_PER_MIB


def read_cpu_temp_file(temp_file: Path | None) -> float | None:
    """Read optional CPU package Celsius exported by a sensor bridge file."""
    if temp_file is None or not temp_file.exists():
        return None
    with contextlib.suppress(OSError, ValueError):
        raw = temp_file.read_text(encoding="utf-8").strip()
        return float(raw)
    return None


class WindowsNativeSensor:
    """Live host telemetry combining NVML, Win32 activity state, and Ollama VRAM accounting."""

    def __init__(
        self,
        ollama_hosts: Sequence[str] = ("http://127.0.0.1:11435", "http://127.0.0.1:11434"),
        managed_pids_fn: Callable[[], set[int]] | None = None,
        cpu_temp_file: Path | None = None,
    ) -> None:
        self._nvml = NvmlProbe()
        self._ollama_hosts = tuple(ollama_hosts)
        self._managed_pids_fn = managed_pids_fn
        env_temp = os.environ.get("ALOS_CPU_TEMP_FILE")
        self._cpu_temp_file = cpu_temp_file or (Path(env_temp) if env_temp else None)

    @property
    def nvml_available(self) -> bool:
        """True when native NVML GPU telemetry is active."""
        return self._nvml.available

    def _compute_managed_vram(self, compute_procs: dict[int, int]) -> int:
        reported_mb = query_ollama_vram_mb(self._ollama_hosts)
        tracked_pids = self._managed_pids_fn() if self._managed_pids_fn else set()
        pid_mb = sum(mb for pid, mb in compute_procs.items() if pid in tracked_pids)
        return max(reported_mb, pid_mb)

    def sample(self) -> TelemetrySnapshot:
        """Collect an atomic host telemetry snapshot in-process."""
        gpu_util, used_mb, total_mb = self._nvml.read_utilization_and_memory()
        compute_procs = self._nvml.read_compute_processes()
        managed_mb = self._compute_managed_vram(compute_procs)
        return TelemetrySnapshot(
            gpu_temp_c=self._nvml.read_gpu_temp(),
            vram_temp_c=self._nvml.read_vram_temp(),
            cpu_temp_c=read_cpu_temp_file(self._cpu_temp_file),
            gpu_util_pct=gpu_util,
            total_vram_mb=total_mb,
            used_vram_mb=used_mb,
            managed_vram_mb=min(used_mb, managed_mb) if used_mb else managed_mb,
            compute_pids=tuple(sorted(compute_procs)),
            d3d_fullscreen=query_win32_d3d_fullscreen(),
            user_idle_seconds=query_win32_idle_seconds(),
            blocked_process=None,
        )


class ScriptedSensor:
    """Deterministic fault-injection sensor for testing spin-down and thermal hysteresis."""

    def __init__(self, initial: TelemetrySnapshot | None = None) -> None:
        self._current = initial or TelemetrySnapshot(
            gpu_temp_c=44.0,
            vram_temp_c=52.0,
            cpu_temp_c=48.0,
            gpu_util_pct=0,
            total_vram_mb=16303,
            used_vram_mb=1600,
            managed_vram_mb=0,
            d3d_fullscreen=False,
            user_idle_seconds=900.0,
        )
        self._queue: deque[TelemetrySnapshot] = deque()

    def push(self, *snapshots: TelemetrySnapshot) -> None:
        """Queue one or more snapshots to be yielded sequentially on ``sample()``."""
        self._queue.extend(snapshots)

    def update(self, **changes: Any) -> TelemetrySnapshot:
        """Mutate fields on the current steady-state snapshot and return it."""
        self._current = replace(self._current, **changes)
        return self._current

    def sample(self) -> TelemetrySnapshot:
        """Pop next scripted reading if queued, else return current steady-state reading."""
        if self._queue:
            self._current = self._queue.popleft()
        return self._current


class FaultOverlaySensor:
    """Wraps a live sensor (e.g. RTX 5080 NVML) while allowing synthetic stimulus overrides."""

    def __init__(self, backing: SensorProvider) -> None:
        self._backing = backing
        self._overrides: dict[str, Any] = {}

    def inject(self, **overrides: Any) -> None:
        """Apply synthetic field overrides (e.g., ``d3d_fullscreen=True``) over live readings."""
        self._overrides.update(overrides)

    def clear(self) -> None:
        """Remove all synthetic overrides and return pure hardware telemetry."""
        self._overrides.clear()

    def sample(self) -> TelemetrySnapshot:
        """Sample live hardware and overlay any injected stimulus fields."""
        live = self._backing.sample()
        return replace(live, **self._overrides) if self._overrides else live
