"""RED-first unit tests for SwarmBoundaryAdapter and CrewConfigLoader use cases (PR-12e)."""

from __future__ import annotations

from pathlib import Path

import pytest

from alos.adapters.outbound.swarm import SwarmBoundaryAdapter
from alos.application.use_cases.crews import CrewAgentSpec, CrewConfigLoader, CrewTaskSpec
from alos.crews.crews.code_quality_crew import CodeQualityCrew
from alos.crews.crews.obsidian_graph_crew import ObsidianGraphSynthesizerCrew
from alos.crews.crews.speckit_architect_crew import SpecKitArchitectCrew
from alos.swarm import dispatcher, queue, sandbox
from alos.swarm.sensors import ScriptedSensor


@pytest.mark.mocked
def test_swarm_boundary_adapter_preserves_monkeypatch_contracts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify SwarmBoundaryAdapter delegates dynamically to preserve test monkeypatches."""
    adapter = SwarmBoundaryAdapter()
    monkeypatch.setattr(dispatcher, "gpu_stats", lambda: (42, 4096, 16384))
    monkeypatch.setattr(dispatcher, "running_processes", lambda: '"python.exe","123"')
    monkeypatch.setattr(dispatcher, "execute", lambda run, force=False: ("ok", f"forced={force}"))

    assert adapter.probe_gpu_stats() == (42, 4096, 16384)
    assert "python.exe" in adapter.list_running_processes()
    assert adapter.gate_check(dispatcher.Ollama(), ["python.exe"], 9000) is not None
    run_obj = dispatcher.Run(run_dir=tmp_path, manifest={"jobs": []}, roster={}, home=tmp_path)
    assert adapter.execute_run(run_obj, force=True) == ("ok", "forced=True")

    monkeypatch.setattr(sandbox, "DOCKER", "fake-docker")
    monkeypatch.setattr(
        sandbox.subprocess,
        "run",
        lambda argv, **kw: type(
            "R", (), {"returncode": 0, "stdout": f"ok:{argv[0]}", "stderr": ""}
        )(),
    )
    monkeypatch.setattr(sandbox, "check_job", lambda job, limits: {"job": job["id"], "ok": True})
    code, out = adapter.run_container(["box", "--version"], "c1", 5.0)
    assert (code, out) == (0, "ok:box")
    assert adapter.check_sandbox_job({"id": "j1"}, sandbox.Limits()) == {"job": "j1", "ok": True}

    gov = adapter.create_governor(sensor=ScriptedSensor())
    assert gov is not None
    sq = adapter.open_sticky_queue(
        f"sqlite:///{(tmp_path / 'q.db').as_posix()}", config=queue.QueueConfig()
    )
    assert isinstance(sq, queue.StickyEpochQueue)
    sq.db.dispose()


@pytest.mark.mocked
def test_crew_config_loader_and_crews_deduplication(tmp_path: Path) -> None:
    """Verify pure CrewConfigLoader injection and backwards-compatible Crew facades."""
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "agents.yaml").write_text("a1:\n  role: Auditor\n", encoding="utf-8")

    loader = CrewConfigLoader(
        config_dir=cfg_dir, parser=lambda raw: {"static_analyzer": {"role": "Parsed"}}
    )
    assert loader.load("agents.yaml") == {"static_analyzer": {"role": "Parsed"}}
    assert loader.load("missing.yaml") == {}
    assert CrewConfigLoader(config_dir=cfg_dir, parser=lambda raw: None).load("agents.yaml") == {}
    assert loader.get_agent_spec(loader.load("agents.yaml"), "a1") == CrewAgentSpec(
        role="A1", goal="Achieve goals for a1", backstory="Backstory for a1"
    )
    assert loader.get_agent_spec(loader.load("agents.yaml"), "static_analyzer").role == "Parsed"
    assert loader.get_task_spec({}, "draft").agent == "spec_architect"
    assert isinstance(CrewTaskSpec(description="d", expected_output="e", agent="a"), CrewTaskSpec)

    assert CodeQualityCrew(spec_loader=loader).run("alos")["agent"] == "Parsed"
    assert ObsidianGraphSynthesizerCrew(spec_loader=loader).run("vault")["status"] == "SUCCESS"
    assert SpecKitArchitectCrew(spec_loader=loader).run("goal")["status"] == "SUCCESS"
