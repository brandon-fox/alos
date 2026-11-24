"""Unit tests for native host telemetry sensors and FaultOverlaySensor (Spec 031)."""

from __future__ import annotations

from pathlib import Path

from alos.swarm.sensors import (
    FaultOverlaySensor,
    ScriptedSensor,
    TelemetrySnapshot,
    WindowsNativeSensor,
    query_ollama_vram_mb,
    read_cpu_temp_file,
)


def test_fault_overlay_and_cpu_temp_bridge_and_live_nvml(tmp_path: Path) -> None:
    """Verify FaultOverlaySensor overrides, scripted stream, and live WindowsNativeSensor."""
    temp_file = tmp_path / "cpu_temp.txt"
    temp_file.write_text("67.5\n", encoding="utf-8")
    assert read_cpu_temp_file(temp_file) == 67.5
    assert query_ollama_vram_mb(()) == 0
    assert TelemetrySnapshot(used_vram_mb=2200, managed_vram_mb=200).foreign_vram_mb == 2000
    scripted = ScriptedSensor()
    scripted.push(TelemetrySnapshot(gpu_temp_c=51.0))
    assert scripted.sample().gpu_temp_c == 51.0
    scripted.update(gpu_temp_c=42.0)
    assert scripted.sample().gpu_temp_c == 42.0
    live = WindowsNativeSensor(ollama_hosts=(), cpu_temp_file=temp_file)
    overlay = FaultOverlaySensor(live)
    base = overlay.sample()
    assert base.cpu_temp_c == 67.5
    if live.nvml_available:
        assert base.total_vram_mb > 0
    overlay.inject(d3d_fullscreen=True)
    assert overlay.sample().d3d_fullscreen is True
    overlay.clear()
    assert overlay.sample().d3d_fullscreen == base.d3d_fullscreen
