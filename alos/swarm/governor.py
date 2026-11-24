"""Preemptible Host Governor, Schmitt-trigger thermal FSM, and Managed Model Epoch Spinner.

Spec: specs/031-preemptible-compute-governor/spec.md (FR-002, FR-003, FR-004, FR-005)
ADR: docs/adr/0014-adopt-preemptible-host-governor-and-sticky-model-epoch-queue.md
"""

from __future__ import annotations

import contextlib
import os
import subprocess  # nosec B404
import threading
import time
import urllib.error
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from enum import Enum

from alos.swarm.dispatcher import Ollama
from alos.swarm.sensors import (
    SensorProvider,
    TelemetrySnapshot,
    query_win32_free_commit_mb,
)


class GovernorState(str, Enum):
    """Lifecycle states of the local compute governor."""

    ARMED_IDLE = "ARMED_IDLE"
    WARM_ACTIVE = "WARM_ACTIVE"
    WARM_LINGER = "WARM_LINGER"
    THROTTLED = "THROTTLED"
    COOLING_CUTOFF = "COOLING_CUTOFF"
    USER_PREEMPTED = "USER_PREEMPTED"


@dataclass(frozen=True)
class HysteresisConfig:
    """Schmitt-trigger trip/recovery thresholds and dwell timers (tuned for RTX 5080 16GB)."""

    gpu_cutoff_c: float = 82.0
    vram_cutoff_c: float = 94.0
    cpu_cutoff_c: float = 92.0
    gpu_recover_c: float = 58.0
    vram_recover_c: float = 76.0
    cpu_recover_c: float = 60.0
    cooling_dwell_s: float = 180.0

    gpu_throttle_c: float = 75.0
    vram_throttle_c: float = 88.0
    cpu_throttle_c: float = 85.0
    active_desk_idle_s: float = 60.0
    gpu_unthrottle_c: float = 65.0
    cpu_unthrottle_c: float = 72.0
    throttle_dwell_s: float = 120.0

    foreign_vram_limit_mb: int = 4608
    foreign_vram_recover_mb: int = 3584
    min_free_commit_mb: int = 512
    recover_free_commit_mb: int = 896
    preempt_recover_idle_s: float = 300.0

    warm_linger_s: float = 600.0
    evict_grace_s: float = 1.2
    evict_vram_floor_mb: int = 128


@dataclass(frozen=True)
class ModelTierSpec:
    """Per-tier Ollama serving configuration for single-GPU warm epochs."""

    tier: str
    model: str
    slots: int = 4
    num_ctx: int = 8192
    kv_cache_type: str = "q8_0"
    keep_alive: str = "10m"
    fallback_models: tuple[str, ...] = ()


DEFAULT_MODEL_TIERS: dict[str, ModelTierSpec] = {
    "fast_coder": ModelTierSpec(
        tier="fast_coder",
        model="qwen2.5-coder:7b-instruct",
        slots=4,
        num_ctx=8192,
        fallback_models=(
            "qwen2.5-coder:3b",
            "qwen2.5-coder:1.5b",
            "qwen2.5-coder:0.5b",
            "llama3.2:latest",
        ),
    ),
    "reasoner": ModelTierSpec(
        tier="reasoner",
        model="gemma4:12b",
        slots=4,
        num_ctx=8192,
        fallback_models=(
            "qwen2.5-coder:7b-instruct",
            "qwen2.5-coder:3b",
            "qwen2.5-coder:1.5b",
            "qwen2.5-coder:0.5b",
            "llama3.2:latest",
        ),
    ),
    "architect": ModelTierSpec(
        tier="architect",
        model="qwen3-coder:30b",
        slots=1,
        num_ctx=8192,
        fallback_models=(
            "gemma4:12b",
            "qwen2.5-coder:7b-instruct",
            "qwen2.5-coder:3b",
            "qwen2.5-coder:1.5b",
            "qwen2.5-coder:0.5b",
        ),
    ),
    "embed": ModelTierSpec(
        tier="embed", model="nomic-embed-text:latest", slots=4, num_ctx=8192, kv_cache_type="f16"
    ),
}


def is_embedding_model(model_name: str, tier_name: str | None = None) -> bool:
    """Return True when the tier or Ollama model tag uses ``/api/embed`` instead of generate."""
    return tier_name == "embed" or "embed" in model_name.lower()


@dataclass(frozen=True)
class EvictionReport:
    """Measured outcome of a VRAM spin-down operation."""

    elapsed_s: float
    graceful_unloaded: bool
    tree_killed: bool
    remaining_managed_vram_mb: int


@dataclass(frozen=True)
class GovernorTransition:
    """Result of one ``HostGovernor.evaluate()`` tick."""

    previous_state: GovernorState
    state: GovernorState
    reason: str
    snapshot: TelemetrySnapshot
    eviction: EvictionReport | None = None

    @property
    def can_pull_work(self) -> bool:
        """True when queue workers are permitted to lease and execute jobs."""
        return self.state in (
            GovernorState.ARMED_IDLE,
            GovernorState.WARM_ACTIVE,
            GovernorState.WARM_LINGER,
            GovernorState.THROTTLED,
        )


def is_usage_preempted(snap: TelemetrySnapshot, cfg: HysteresisConfig) -> str | None:
    """Return preemption reason when gaming, blocked apps, VRAM, or OS commit cross limits."""
    if snap.d3d_fullscreen:
        return "Direct3D fullscreen / presentation activity detected"
    if snap.blocked_process:
        return f"blocked process active: {snap.blocked_process}"
    if snap.foreign_vram_mb > cfg.foreign_vram_limit_mb:
        return f"foreign GPU memory {snap.foreign_vram_mb} MiB > {cfg.foreign_vram_limit_mb} MiB"
    if snap.free_commit_mb is not None:
        non_managed_free = snap.free_commit_mb + snap.managed_vram_mb
        if non_managed_free < cfg.min_free_commit_mb:
            return f"OS commit memory low ({non_managed_free} MiB < {cfg.min_free_commit_mb} MiB)"
    return None


def has_usage_recovered(snap: TelemetrySnapshot, cfg: HysteresisConfig) -> bool:
    """True when gaming/foreign VRAM/commit cleared and user has been idle past recovery window."""
    no_game = not snap.d3d_fullscreen and snap.blocked_process is None
    vram_ok = snap.foreign_vram_mb <= cfg.foreign_vram_recover_mb
    commit_ok = (
        snap.free_commit_mb is None
        or (snap.free_commit_mb + snap.managed_vram_mb) >= cfg.recover_free_commit_mb
    )
    idle_ok = snap.user_idle_seconds >= cfg.preempt_recover_idle_s
    return no_game and vram_ok and commit_ok and idle_ok


def is_thermal_cutoff(snap: TelemetrySnapshot, cfg: HysteresisConfig) -> str | None:
    """Return cutoff reason when GPU core, GDDR memory, or CPU package exceeds hard ceiling."""
    if snap.gpu_temp_c is not None and snap.gpu_temp_c >= cfg.gpu_cutoff_c:
        return f"GPU temperature {snap.gpu_temp_c:.1f}C >= {cfg.gpu_cutoff_c:.1f}C"
    if snap.vram_temp_c is not None and snap.vram_temp_c >= cfg.vram_cutoff_c:
        return f"VRAM temperature {snap.vram_temp_c:.1f}C >= {cfg.vram_cutoff_c:.1f}C"
    if snap.cpu_temp_c is not None and snap.cpu_temp_c >= cfg.cpu_cutoff_c:
        return f"CPU temperature {snap.cpu_temp_c:.1f}C >= {cfg.cpu_cutoff_c:.1f}C"
    return None


def has_thermal_recovered(snap: TelemetrySnapshot, cfg: HysteresisConfig) -> bool:
    """True when all present temperature sensors sit at or below recovery floor."""
    gpu_ok = snap.gpu_temp_c is None or snap.gpu_temp_c <= cfg.gpu_recover_c
    vram_ok = snap.vram_temp_c is None or snap.vram_temp_c <= cfg.vram_recover_c
    cpu_ok = snap.cpu_temp_c is None or snap.cpu_temp_c <= cfg.cpu_recover_c
    return gpu_ok and vram_ok and cpu_ok


def is_thermal_throttled(snap: TelemetrySnapshot, cfg: HysteresisConfig) -> bool:
    """True when elevated GPU, VRAM, or CPU temperatures trigger thermal throttling."""
    gpu_hot = snap.gpu_temp_c is not None and snap.gpu_temp_c >= cfg.gpu_throttle_c
    vram_hot = snap.vram_temp_c is not None and snap.vram_temp_c >= cfg.vram_throttle_c
    cpu_hot = snap.cpu_temp_c is not None and snap.cpu_temp_c >= cfg.cpu_throttle_c
    return gpu_hot or vram_hot or cpu_hot


def is_throttled(snap: TelemetrySnapshot, cfg: HysteresisConfig) -> str | None:
    """Return throttle reason on elevated thermals or light interactive desktop input."""
    if snap.gpu_temp_c is not None and snap.gpu_temp_c >= cfg.gpu_throttle_c:
        return f"GPU warm ({snap.gpu_temp_c:.1f}C >= {cfg.gpu_throttle_c:.1f}C)"
    if snap.vram_temp_c is not None and snap.vram_temp_c >= cfg.vram_throttle_c:
        return f"VRAM warm ({snap.vram_temp_c:.1f}C >= {cfg.vram_throttle_c:.1f}C)"
    if snap.cpu_temp_c is not None and snap.cpu_temp_c >= cfg.cpu_throttle_c:
        return f"CPU warm ({snap.cpu_temp_c:.1f}C >= {cfg.cpu_throttle_c:.1f}C)"
    if snap.user_idle_seconds < cfg.active_desk_idle_s:
        return f"interactive desktop input ({snap.user_idle_seconds:.0f}s idle)"
    return None


def has_throttle_recovered(snap: TelemetrySnapshot, cfg: HysteresisConfig) -> bool:
    """True when thermals cooled below unthrottle mark and desktop input went quiet."""
    gpu_ok = snap.gpu_temp_c is None or snap.gpu_temp_c <= cfg.gpu_unthrottle_c
    cpu_ok = snap.cpu_temp_c is None or snap.cpu_temp_c <= cfg.cpu_unthrottle_c
    idle_ok = snap.user_idle_seconds >= cfg.active_desk_idle_s
    return gpu_ok and cpu_ok and idle_ok


def kill_process_tree(pid: int) -> bool:
    """Terminate ``pid`` and all child runners (critical on Windows to release CUDA VRAM)."""
    if pid <= 0:
        return False
    if os.name == "nt":
        cmd = ["taskkill", "/PID", str(pid), "/T", "/F"]
        # Fixed argument list without shell expansion; targets our own spawned Ollama PID.
        res = subprocess.run(cmd, capture_output=True, timeout=15, check=False)  # noqa: S603  # nosec B603
        return res.returncode == 0
    with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
        os.kill(pid, 15)
        return True
    return False


class ContainerPauser:
    """Freezes and resumes registered Docker devcontainer workers on preemption."""

    def __init__(
        self,
        runner: Callable[[list[str]], int] | None = None,
    ) -> None:
        self._containers: set[str] = set()
        self._paused: set[str] = set()
        self._runner = runner or self._default_runner

    @staticmethod
    def _default_runner(cmd: list[str]) -> int:
        with contextlib.suppress(OSError, subprocess.SubprocessError):
            # Fixed docker CLI invocation with explicit container names; no shell.
            res = subprocess.run(cmd, capture_output=True, timeout=10, check=False)  # noqa: S603  # nosec B603
            return res.returncode
        return 1

    def register(self, container_name: str) -> None:
        """Track an active worker container for preemption pause/unpause."""
        self._containers.add(container_name)

    def unregister(self, container_name: str) -> None:
        """Stop tracking a worker container."""
        self._containers.discard(container_name)
        self._paused.discard(container_name)

    @property
    def paused_containers(self) -> frozenset[str]:
        """Currently paused container identifiers."""
        return frozenset(self._paused)

    def pause_all(self) -> list[str]:
        """Run ``docker pause`` on registered containers not yet paused."""
        targets = sorted(self._containers - self._paused)
        if targets and self._runner(["docker", "pause", *targets]) == 0:
            self._paused.update(targets)
        return targets

    def unpause_all(self) -> list[str]:
        """Run ``docker unpause`` on previously paused worker containers."""
        targets = sorted(self._paused)
        if targets and self._runner(["docker", "unpause", *targets]) == 0:
            self._paused.clear()
        return targets


class ModelSpinner:
    """Manages an isolated Ollama epoch server with flash attention, q8_0 KV, and fast eviction."""

    def __init__(
        self,
        port: int = 11435,
        stock_host: str = "http://127.0.0.1:11434",
        tiers: Mapping[str, ModelTierSpec] | None = None,
        evict_grace_s: float = 1.2,
        evict_vram_floor_mb: int = 128,
    ) -> None:
        self.port = port
        self.host = f"http://127.0.0.1:{port}"
        self.stock_host = stock_host
        self.tiers = dict(tiers or DEFAULT_MODEL_TIERS)
        self.evict_grace_s = evict_grace_s
        self.evict_vram_floor_mb = evict_vram_floor_mb
        self._proc: subprocess.Popen[bytes] | None = None
        self._active_spec: ModelTierSpec | None = None

    @property
    def active_tier(self) -> str | None:
        """Name of the currently warm model tier, or None when cold."""
        return self._active_spec.tier if self._active_spec else None

    @property
    def active_model(self) -> str | None:
        """Tag of the currently warm Ollama model, or None when cold."""
        return self._active_spec.model if self._active_spec else None

    @property
    def server_pid(self) -> int | None:
        """OS PID of the managed ``ollama serve`` process if running."""
        if self._proc is not None and self._proc.poll() is None:
            return self._proc.pid
        return None

    def managed_pids(self) -> set[int]:
        """Known PIDs owned by this spinner."""
        return {self._proc.pid} if self._proc is not None and self._proc.poll() is None else set()

    def _spawn_server(self, spec: ModelTierSpec) -> Ollama:
        client = Ollama(self.host)
        env = dict(
            os.environ,
            OLLAMA_HOST=f"127.0.0.1:{self.port}",
            OLLAMA_NUM_PARALLEL=str(spec.slots),
            OLLAMA_FLASH_ATTENTION="1",
            OLLAMA_KV_CACHE_TYPE=spec.kv_cache_type,
            OLLAMA_MAX_LOADED_MODELS="1",
        )
        # Fixed executable list resolved from PATH without shell invocation.
        self._proc = subprocess.Popen(  # nosec B603 B607
            ["ollama", "serve"],  # noqa: S607
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline:
            with contextlib.suppress(OSError, ValueError):
                client.call("/api/version", timeout=0.5)
                return client
            time.sleep(0.15)
        self._stop_process_tree()
        raise RuntimeError(f"managed Ollama server failed to start on {self.host}")

    def _needs_server_restart(self, spec: ModelTierSpec) -> bool:
        if self._proc is None or self._proc.poll() is not None:
            return True
        if self._active_spec is None:
            return False
        return (
            self._active_spec.slots != spec.slots
            or self._active_spec.kv_cache_type != spec.kv_cache_type
        )

    @staticmethod
    def _is_oom_failure(detail: str) -> bool:
        low = detail.lower()
        markers = ("out of memory", "cudamalloc", "mem_buffer", "0xc0000409", "failed to allocate")
        return any(m in low for m in markers)

    def _warm_model(self, client: Ollama, spec: ModelTierSpec) -> str | None:
        """Warm ``spec.model`` and its prompt buffer in VRAM; return OOM detail on failure."""
        try:
            if is_embedding_model(spec.model, spec.tier):
                client.call(
                    "/api/embed",
                    {"model": spec.model, "input": "ok", "keep_alive": spec.keep_alive},
                    timeout=60.0,
                )
                return None
            client.call(
                "/api/generate",
                {
                    "model": spec.model,
                    "prompt": "ok",
                    "stream": False,
                    "keep_alive": spec.keep_alive,
                    "options": {"num_ctx": spec.num_ctx, "num_predict": 1},
                },
                timeout=60.0,
            )
            return None
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if self._is_oom_failure(detail):
                return detail
            raise RuntimeError(f"Ollama warm-load HTTP {exc.code}: {detail}") from exc

    def _query_stock_model_sizes_mb(self) -> dict[str, int]:
        with contextlib.suppress(OSError, ValueError):
            tags = Ollama(self.stock_host).call("/api/tags", timeout=1.5).get("models", [])
            return {
                str(m.get("name", "")): int(m.get("size", 0)) // (1024 * 1024)
                for m in tags
                if m.get("name")
            }
        return {}

    def _select_commit_fitting_candidate(
        self,
        spec: ModelTierSpec,
        fallback_queue: list[str],
        sizes_mb: Mapping[str, int],
    ) -> ModelTierSpec:
        free_mb = query_win32_free_commit_mb()
        primary_mb = sizes_mb.get(spec.model)
        if free_mb is None or primary_mb is None or primary_mb + 1800 <= free_mb:
            return spec
        chosen = spec.model
        while fallback_queue:
            chosen = fallback_queue.pop(0)
            if sizes_mb.get(chosen, 0) + 1500 <= free_mb:
                return replace(spec, model=chosen, slots=min(spec.slots, 2), num_ctx=4096)
        return replace(spec, model=chosen, slots=1, num_ctx=2048)

    def _prepare_candidates(self, spec: ModelTierSpec) -> tuple[ModelTierSpec, list[str]]:
        if not spec.fallback_models:
            return spec, []
        sizes_mb = self._query_stock_model_sizes_mb()
        fallback_queue = [m for m in spec.fallback_models if m in sizes_mb]
        if not fallback_queue:
            return spec, []
        return self._select_commit_fitting_candidate(spec, fallback_queue, sizes_mb), fallback_queue

    def _next_degraded_spec(
        self, candidate: ModelTierSpec, fallback_queue: list[str]
    ) -> ModelTierSpec | None:
        if candidate.slots > 1:
            return replace(candidate, slots=max(1, candidate.slots // 2))
        if candidate.num_ctx > 2048:
            return replace(candidate, num_ctx=max(2048, candidate.num_ctx // 2))
        if fallback_queue:
            next_model = fallback_queue.pop(0)
            return replace(candidate, model=next_model, slots=2, num_ctx=4096)
        return None

    def _start_and_warm(self, spec: ModelTierSpec, warm_load: bool) -> tuple[Ollama, ModelTierSpec]:
        candidate, fallback_queue = self._prepare_candidates(spec)
        while True:
            if self._needs_server_restart(candidate):
                self._stop_process_tree()
                client = self._spawn_server(candidate)
            else:
                client = Ollama(self.host)
            if not warm_load:
                return client, candidate
            oom_detail = self._warm_model(client, candidate)
            if oom_detail is None:
                return client, candidate
            degraded = self._next_degraded_spec(candidate, fallback_queue)
            self._stop_process_tree()
            if degraded is None:
                raise RuntimeError(f"Ollama CUDA OOM even at 1 slot: {oom_detail}")
            candidate = degraded

    def ensure_tier(self, tier_name: str, warm_load: bool = True) -> Ollama:
        """Ensure ``tier_name`` is serving on our managed port and pre-warmed in VRAM."""
        spec = self.tiers.get(tier_name)
        if spec is None:
            raise KeyError(f"unknown model tier {tier_name!r}")
        if (
            self._active_spec is not None
            and self._active_spec.tier == tier_name
            and self._proc is not None
            and self._proc.poll() is None
        ):
            return Ollama(self.host)
        if self._active_spec is None:
            self._unload_stock_server()
        else:
            self._request_unload(Ollama(self.host), self._active_spec.model)
            self._stop_process_tree()
            self._active_spec = None
        client, effective_spec = self._start_and_warm(spec, warm_load)
        self._active_spec = effective_spec
        return client

    def refresh_keep_alive(self) -> bool:
        """Extend the loaded model's warm lease during ``WARM_LINGER``."""
        if self._active_spec is None:
            return False
        endpoint = (
            "/api/embed"
            if is_embedding_model(self._active_spec.model, self._active_spec.tier)
            else "/api/generate"
        )
        body: dict[str, str] = {"model": self._active_spec.model, "keep_alive": "10m"}
        body["input" if endpoint == "/api/embed" else "prompt"] = ""
        with contextlib.suppress(OSError, ValueError):
            Ollama(self.host).call(endpoint, body, timeout=5.0)
            return True
        return False

    def _request_unload(self, client: Ollama, model_name: str) -> bool:
        endpoint = "/api/embed" if is_embedding_model(model_name) else "/api/generate"
        with contextlib.suppress(OSError, ValueError):
            client.call(
                endpoint,
                {"model": model_name, "keep_alive": 0},
                timeout=self.evict_grace_s,
            )
            return True
        return False

    def _unload_stock_server(self) -> None:
        stock = Ollama(self.stock_host)
        with contextlib.suppress(OSError, ValueError):
            for entry in stock.call("/api/ps", timeout=0.6).get("models", []):
                name = str(entry.get("name", ""))
                if name:
                    self._request_unload(stock, name)

    def _stop_process_tree(self) -> bool:
        proc = self._proc
        self._proc = None
        if proc is None:
            return False
        killed = kill_process_tree(proc.pid)
        with contextlib.suppress(subprocess.TimeoutExpired, OSError):
            proc.wait(timeout=3.0)
        return killed

    def evict_all(self, sensor: SensorProvider | None = None) -> EvictionReport:
        """Unload active weights and forcibly kill the runner tree so 0 MB VRAM remains."""
        started = time.monotonic()
        graceful = False
        if self._active_spec is not None:
            graceful = self._request_unload(Ollama(self.host), self._active_spec.model)
        self._unload_stock_server()
        self._active_spec = None
        tree_killed = self._stop_process_tree()
        remaining_mb = 0
        if sensor is not None:
            deadline = started + max(0.3, self.evict_grace_s)
            while True:
                remaining_mb = sensor.sample().managed_vram_mb
                if remaining_mb <= self.evict_vram_floor_mb or time.monotonic() >= deadline:
                    break
                time.sleep(0.05)
        return EvictionReport(
            elapsed_s=round(time.monotonic() - started, 3),
            graceful_unloaded=graceful,
            tree_killed=tree_killed,
            remaining_managed_vram_mb=remaining_mb,
        )


@dataclass
class HostGovernor:
    """Evaluates telemetry with Schmitt-trigger hysteresis and coordinates spin-down/up."""

    sensor: SensorProvider
    spinner: ModelSpinner
    pauser: ContainerPauser = field(default_factory=ContainerPauser)
    config: HysteresisConfig = field(default_factory=HysteresisConfig)
    clock: Callable[[], float] = time.monotonic
    state: GovernorState = GovernorState.ARMED_IDLE
    cancel_event: threading.Event = field(default_factory=threading.Event)
    _recovery_started_at: float | None = field(default=None, init=False, repr=False)
    _linger_started_at: float | None = field(default=None, init=False, repr=False)

    def _check_dwell(self, condition_ok: bool, now: float, required_s: float) -> bool:
        if not condition_ok:
            self._recovery_started_at = None
            return False
        if self._recovery_started_at is None:
            self._recovery_started_at = now
        return (now - self._recovery_started_at) >= required_s

    def _resolve_blocked_state(
        self, snap: TelemetrySnapshot, now: float
    ) -> tuple[GovernorState, str]:
        if self.state == GovernorState.USER_PREEMPTED:
            if has_usage_recovered(snap, self.config):
                self._recovery_started_at = None
                return GovernorState.ARMED_IDLE, "user activity cleared and idle window satisfied"
            return GovernorState.USER_PREEMPTED, "holding preemption until gaming/VRAM/idle clear"
        cooled = self._check_dwell(
            has_thermal_recovered(snap, self.config), now, self.config.cooling_dwell_s
        )
        if cooled:
            self._recovery_started_at = None
            return GovernorState.ARMED_IDLE, "thermals held below recovery floor"
        return GovernorState.COOLING_CUTOFF, "cooling down toward hysteresis recovery floor"

    def _resolve_open_state(
        self, snap: TelemetrySnapshot, now: float, has_queued_work: bool
    ) -> tuple[GovernorState, str]:
        throttle_why = is_throttled(snap, self.config)
        if throttle_why:
            self._recovery_started_at = None
            return GovernorState.THROTTLED, throttle_why
        if self.state == GovernorState.THROTTLED:
            settled = self._check_dwell(
                has_throttle_recovered(snap, self.config), now, self.config.throttle_dwell_s
            )
            if not settled:
                return GovernorState.THROTTLED, "holding throttle dwell window"
            self._recovery_started_at = None
        return self._resolve_warm_or_idle(now, has_queued_work)

    def _resolve_warm_or_idle(self, now: float, has_queued_work: bool) -> tuple[GovernorState, str]:
        if has_queued_work:
            self._linger_started_at = None
            return GovernorState.WARM_ACTIVE, "gate open and work queued"
        if self.spinner.active_tier is not None or self.state in (
            GovernorState.WARM_ACTIVE,
            GovernorState.WARM_LINGER,
        ):
            if self._linger_started_at is None:
                self._linger_started_at = now
            if (now - self._linger_started_at) < self.config.warm_linger_s:
                return GovernorState.WARM_LINGER, "queue empty; keeping active model warm"
            self._linger_started_at = None
            return GovernorState.ARMED_IDLE, "warm linger expired; returning to cold idle"
        return GovernorState.ARMED_IDLE, "armed and waiting for queued work"

    def _next_state(
        self, snap: TelemetrySnapshot, now: float, has_queued_work: bool
    ) -> tuple[GovernorState, str]:
        usage_why = is_usage_preempted(snap, self.config)
        if usage_why:
            self._recovery_started_at = None
            self._linger_started_at = None
            return GovernorState.USER_PREEMPTED, usage_why
        thermal_why = is_thermal_cutoff(snap, self.config)
        if thermal_why:
            self._recovery_started_at = None
            self._linger_started_at = None
            return GovernorState.COOLING_CUTOFF, thermal_why
        if self.state in (GovernorState.USER_PREEMPTED, GovernorState.COOLING_CUTOFF):
            return self._resolve_blocked_state(snap, now)
        return self._resolve_open_state(snap, now, has_queued_work)

    def _apply_transition_effects(
        self, prev: GovernorState, target: GovernorState
    ) -> EvictionReport | None:
        hard_stop = target in (GovernorState.USER_PREEMPTED, GovernorState.COOLING_CUTOFF)
        if hard_stop and prev != target:
            self.cancel_event.set()
            self.pauser.pause_all()
            return self.spinner.evict_all(self.sensor)
        if prev == GovernorState.WARM_LINGER and target == GovernorState.ARMED_IDLE:
            return self.spinner.evict_all(self.sensor)
        if prev in (GovernorState.USER_PREEMPTED, GovernorState.COOLING_CUTOFF) and not hard_stop:
            self.cancel_event.clear()
            self.pauser.unpause_all()
        return None

    def evaluate(self, has_queued_work: bool = False) -> GovernorTransition:
        """Sample sensors once, advance FSM with hysteresis, and execute spin-down/up actions."""
        snap = self.sensor.sample()
        now = self.clock()
        prev = self.state
        target, reason = self._next_state(snap, now, has_queued_work)
        self.state = target
        eviction = self._apply_transition_effects(prev, target)
        return GovernorTransition(
            previous_state=prev,
            state=target,
            reason=reason,
            snapshot=snap,
            eviction=eviction,
        )
