"""Local swarm dispatcher, sandbox, preemptible compute governor, and sticky epoch queue."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from alos.swarm.governor import (
        DEFAULT_MODEL_TIERS,
        ContainerPauser,
        EvictionReport,
        GovernorState,
        GovernorTransition,
        HostGovernor,
        HysteresisConfig,
        ModelSpinner,
        ModelTierSpec,
    )
    from alos.swarm.queue import (
        ComputeRuntimeLoop,
        LeasedJob,
        LoopTickResult,
        PreemptedExecutionError,
        QueueConfig,
        StickyEpochQueue,
    )
    from alos.swarm.sensors import (
        FaultOverlaySensor,
        NvmlProbe,
        ScriptedSensor,
        SensorProvider,
        TelemetrySnapshot,
        WindowsNativeSensor,
    )

_EXPORTS: dict[str, tuple[str, str]] = {
    "DEFAULT_MODEL_TIERS": ("alos.swarm.governor", "DEFAULT_MODEL_TIERS"),
    "ComputeRuntimeLoop": ("alos.swarm.queue", "ComputeRuntimeLoop"),
    "ContainerPauser": ("alos.swarm.governor", "ContainerPauser"),
    "EvictionReport": ("alos.swarm.governor", "EvictionReport"),
    "FaultOverlaySensor": ("alos.swarm.sensors", "FaultOverlaySensor"),
    "GovernorState": ("alos.swarm.governor", "GovernorState"),
    "GovernorTransition": ("alos.swarm.governor", "GovernorTransition"),
    "HostGovernor": ("alos.swarm.governor", "HostGovernor"),
    "HysteresisConfig": ("alos.swarm.governor", "HysteresisConfig"),
    "LeasedJob": ("alos.swarm.queue", "LeasedJob"),
    "LoopTickResult": ("alos.swarm.queue", "LoopTickResult"),
    "ModelSpinner": ("alos.swarm.governor", "ModelSpinner"),
    "ModelTierSpec": ("alos.swarm.governor", "ModelTierSpec"),
    "NvmlProbe": ("alos.swarm.sensors", "NvmlProbe"),
    "PreemptedExecutionError": ("alos.swarm.queue", "PreemptedExecutionError"),
    "QueueConfig": ("alos.swarm.queue", "QueueConfig"),
    "ScriptedSensor": ("alos.swarm.sensors", "ScriptedSensor"),
    "SensorProvider": ("alos.swarm.sensors", "SensorProvider"),
    "StickyEpochQueue": ("alos.swarm.queue", "StickyEpochQueue"),
    "TelemetrySnapshot": ("alos.swarm.sensors", "TelemetrySnapshot"),
    "WindowsNativeSensor": ("alos.swarm.sensors", "WindowsNativeSensor"),
}

__all__ = [
    "DEFAULT_MODEL_TIERS",
    "ComputeRuntimeLoop",
    "ContainerPauser",
    "EvictionReport",
    "FaultOverlaySensor",
    "GovernorState",
    "GovernorTransition",
    "HostGovernor",
    "HysteresisConfig",
    "LeasedJob",
    "LoopTickResult",
    "ModelSpinner",
    "ModelTierSpec",
    "NvmlProbe",
    "PreemptedExecutionError",
    "QueueConfig",
    "ScriptedSensor",
    "SensorProvider",
    "StickyEpochQueue",
    "TelemetrySnapshot",
    "WindowsNativeSensor",
]


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    mod_name, attr_name = target
    return getattr(import_module(mod_name), attr_name)
