"""Expanded domain & edge-case coverage across ALOS packages (Spec 035, FR-010).

Covers CLI lifecycle/archive/vault resolution, pure-Python Obsidian vault & NetworkX graph
fallbacks, SpecRAG BM25Okapi fallback, LocalVectorStore edge cases, native bridge dispatch,
DB rollback/drop, and ModelSpinner / dispatcher helpers to raise branch+line coverage > 90%.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from alos.cli import _resolve_vault_dir
from alos.cli import main as alos_cli_main
from alos.core.graph import ALOSStateGraph  # noqa: F401 - avoid circular init before integrations
from alos.db.session import DatabaseManager
from alos.integrations.speckit.lifecycle import LifecycleState, SpecKitLifecycleManager
from alos.memory.obsidian_graph import ObsidianGraphEngine
from alos.memory.obsidian_vault import ObsidianVaultParser
from alos.memory.spec_rag import SpecRAGIndexer
from alos.memory.vector_store import LocalVectorStore
from alos.native import bridge
from alos.runtime import _probe_database, _probe_home_writable
from alos.swarm import dispatcher
from alos.swarm.dispatcher import Ollama
from alos.swarm.governor import DEFAULT_MODEL_TIERS, ModelSpinner

pytestmark = [pytest.mark.source, pytest.mark.platform_agnostic]


def test_cli_speckit_lifecycle_archive_and_vault_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """FR-010: Exercise CLI speckit lifecycle transition/status, archive/restore, and errors."""
    monkeypatch.chdir(tmp_path)
    spec_dir = tmp_path / "specs" / "001-demo"
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text("# Demo\nFR-001\n", encoding="utf-8")

    # Missing required flags exit 1 cleanly
    for bad_args in (
        ["speckit", "lifecycle", "--action", "transition"],
        ["speckit", "archive"],
        ["speckit", "archive", "--restore"],
    ):
        with pytest.raises(SystemExit) as exc:
            alos_cli_main(bad_args)
        assert exc.value.code == 1

    # Valid status, transition, archive, and restore flows
    for ok_args in (
        ["speckit", "lifecycle", "--feature", "001-demo"],
        [
            "speckit",
            "lifecycle",
            "--action",
            "transition",
            "--feature",
            "001-demo",
            "--target-state",
            "in_progress",
            "--reason",
            "ready",
        ],
        [
            "speckit",
            "lifecycle",
            "--action",
            "transition",
            "--feature",
            "001-demo",
            "--target-state",
            "approved",
        ],
        [
            "speckit",
            "lifecycle",
            "--action",
            "transition",
            "--feature",
            "001-demo",
            "--target-state",
            "completed",
        ],
        ["speckit", "archive", "--feature", "001-demo"],
        ["speckit", "archive", "--restore", "--feature", "001-demo"],
    ):
        with pytest.raises(SystemExit) as exc:
            alos_cli_main(ok_args)
        assert exc.value.code == 0

    # Portable vault fallback when local relative path does not exist
    portable_home = tmp_path / "portable_h"
    (portable_home / "vault").mkdir(parents=True)
    monkeypatch.setenv("ALOS_HOME", str(portable_home))
    resolved = _resolve_vault_dir("nonexistent_local_vault")
    assert Path(resolved) == (portable_home / "vault").resolve()
    _ = capsys.readouterr()


def test_obsidian_vault_and_graph_pure_python_and_mocked_native_branches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-010: Exercise both pure-Python NetworkX/frontmatter and mocked native error fallbacks."""
    from alos.memory import obsidian_graph, obsidian_vault

    vdir = tmp_path / "vault"
    vdir.mkdir()
    (vdir / "Alpha.md").write_text(
        "---\ntags: solo_tag\n---\nLink to [[Beta|B#Top]] #inline1 #solo_tag\n",
        encoding="utf-8",
    )
    (vdir / "Beta.md").write_text("Back to [[Alpha]]\n", encoding="utf-8")

    # Force pure-Python branches
    monkeypatch.setattr(obsidian_vault, "HAS_RUST_NATIVE", False)
    monkeypatch.setattr(obsidian_graph, "HAS_RUST_NATIVE_GRAPH", False)

    parser = ObsidianVaultParser(str(vdir))
    alpha = parser.parse_file(str(vdir / "Alpha.md"))
    assert "solo_tag" in alpha.tags and "inline1" in alpha.tags
    assert alpha.wiki_links == ["Beta"]
    assert len(parser.parse_all()) == 2
    assert ObsidianVaultParser(str(tmp_path / "missing_v")).parse_all() == []

    engine = ObsidianGraphEngine(str(vdir))
    assert engine.get_neighborhood("Alpha", depth=1).nodes == {"Alpha", "Beta"}
    assert engine.get_neighborhood("Unknown", depth=2).nodes == {"Unknown"}

    # Simulate native graph / parser raising an exception -> graceful fallback to Python
    class _BrokenNativeGraph:
        def add_node(self, _n: str) -> None:
            raise RuntimeError("simulated native failure")

    monkeypatch.setattr(obsidian_graph, "HAS_RUST_NATIVE_GRAPH", True)
    monkeypatch.setattr(obsidian_graph, "FastGraphEngine", _BrokenNativeGraph)
    assert ObsidianGraphEngine(str(vdir)).get_neighborhood("Alpha", depth=1).nodes == {
        "Alpha",
        "Beta",
    }


def test_spec_rag_bm25okapi_fallback_and_vector_store_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-010: Exercise SpecRAGIndexer source types + BM25Okapi fallback & LocalVectorStore."""
    from alos.memory import spec_rag

    root = tmp_path / "rag_root"
    (root / "references").mkdir(parents=True)
    (root / "specs").mkdir(parents=True)
    (root / "references" / "ref.md").write_text(
        "# Reference Architecture\nQuantum scheduler hysteresis details.\n", encoding="utf-8"
    )
    (root / "specs" / "s1.md").write_text("# Spec One\nGeneral notes.\n", encoding="utf-8")

    # Force get_bm25_indexer to raise so BM25Okapi fallback executes
    def _broken_bm25() -> object:
        raise RuntimeError("force BM25Okapi fallback")

    monkeypatch.setattr(spec_rag, "get_bm25_indexer", _broken_bm25)
    # Add 3 reference docs so BM25Okapi IDF for "quantum" (1/3 docs) is strictly positive (>0)
    (root / "references" / "other1.md").write_text(
        "# Other Topic One\nUnrelated baseline content.\n", encoding="utf-8"
    )
    (root / "references" / "other2.md").write_text(
        "# Other Topic Two\nSecond unrelated baseline document.\n", encoding="utf-8"
    )
    indexer = SpecRAGIndexer(str(root))
    assert indexer._determine_source_type("other/doc.md") == "general"
    assert indexer.search("quantum", top_k=3, source_filter="reference")[0]["source_type"] == (
        "reference"
    )
    assert indexer.search("", top_k=2)[0]["score"] == 0.0
    assert indexer.search("quantum", top_k=2, source_filter="nonexistent") == []

    # LocalVectorStore edge cases
    assert LocalVectorStore(str(tmp_path / "no_dir")).search("q") == []
    empty_v = tmp_path / "empty_v"
    empty_v.mkdir()
    assert LocalVectorStore(str(empty_v)).search("q") == []
    (empty_v / "note.md").write_text("delta airline booking rule", encoding="utf-8")
    (empty_v / "other1.md").write_text("unrelated schedule item", encoding="utf-8")
    (empty_v / "other2.md").write_text("unrelated groceries list", encoding="utf-8")
    vs = LocalVectorStore(str(empty_v))
    assert vs.search("", top_k=1)[0]["score"] == 0.0
    assert vs.search("delta", top_k=1)[0]["score"] > 0.0


def test_native_bridge_mocked_dispatch_and_db_lifecycle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-010: Verify native bridge dispatches to _NATIVE_MODULE when present & DB rollback/drop."""
    fake_mod = SimpleNamespace(
        FastSafetyEvaluator=lambda: "native_safety",
        FastAuditJournalWriter=lambda p: f"native_journal:{p}",
        FastBM25Indexer=lambda k1, b: ("native_bm25", k1, b),
    )
    monkeypatch.setattr(bridge, "_NATIVE_MODULE", fake_mod)
    assert bridge.get_safety_evaluator() == "native_safety"
    assert bridge.get_journal_writer("a.jsonl") == "native_journal:a.jsonl"
    assert bridge.get_bm25_indexer(1.2, 0.5) == ("native_bm25", 1.2, 0.5)

    # DatabaseManager rollback on exception + drop_all_tables + runtime probe failure
    db = DatabaseManager(f"sqlite:///{(tmp_path / 'cov.db').as_posix()}")
    db.create_all_tables()
    with pytest.raises(RuntimeError, match="abort tx"), db.get_session() as _s:
        raise RuntimeError("abort tx")
    db.drop_all_tables()

    bad_db = _probe_database("sqlite:///Z:/__nonexistent_alos_drive__/bad.db")
    assert bad_db["ok"] is False

    # Lifecycle enum target & corrupt JSON recovery
    from alos.integrations.speckit.lifecycle import InvalidStateTransitionError

    mgr = SpecKitLifecycleManager(root_dir=tmp_path)
    rec_path = mgr._get_record_path("corrupt-feat")
    rec_path.write_text("{not-json", encoding="utf-8")
    assert mgr.get_status("corrupt-feat")["current_state"] == "draft"
    with pytest.raises(InvalidStateTransitionError):
        mgr.transition_state("corrupt-feat", "not_a_valid_state")
    updated = mgr.transition_state("corrupt-feat", LifecycleState.IN_PROGRESS)
    assert updated["current_state"] == "in_progress"


def test_spinner_and_dispatcher_unit_helpers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-010: Cover ModelSpinner warm/refresh/unload helpers and dispatcher gate/run_phase."""
    calls: list[tuple[str, dict[str, object] | None]] = []

    def fake_call(
        self: Ollama, path: str, body: dict[str, object] | None = None, timeout: float = 10.0
    ) -> dict[str, object]:
        calls.append((path, body))
        if path == "/api/ps":
            return {"models": [{"name": "qwen2.5-coder:7b-instruct", "size_vram": 2048 * 2**20}]}
        if path == "/api/tags":
            return {"models": [{"name": m.model} for m in DEFAULT_MODEL_TIERS.values()]}
        if path == "/api/show":
            return {"capabilities": ["thinking"]}
        return {"response": '{"ok": true}', "done_reason": "stop", "eval_count": 4}

    monkeypatch.setattr(Ollama, "call", fake_call)
    spinner = ModelSpinner(port=19999)
    assert spinner.refresh_keep_alive() is False
    spinner._active_spec = DEFAULT_MODEL_TIERS["fast_coder"]
    assert spinner.refresh_keep_alive() is True
    assert spinner._warm_model(Ollama(spinner.host), DEFAULT_MODEL_TIERS["fast_coder"]) is None
    spinner._unload_stock_server()
    assert any(p == "/api/ps" for p, _ in calls)

    # Dispatcher gpu_stats + gate + execute/run_phase/main
    monkeypatch.setattr(dispatcher, "running_processes", lambda: '"game.exe","explorer.exe"')
    assert dispatcher.gate(Ollama(), ["Game.exe"], 4096) == "Game.exe is running"
    monkeypatch.setattr(dispatcher, "running_processes", lambda: "")
    monkeypatch.setattr(dispatcher, "gpu_stats", lambda: (50, 9000, 16384))
    assert "GPU memory in use" in (dispatcher.gate(Ollama(), [], 4096) or "")

    monkeypatch.setattr(dispatcher, "gpu_stats", lambda: (10, 500, 16384))
    monkeypatch.setattr(dispatcher, "DEFAULT_HOST", "http://127.0.0.1:11434")
    run_dir = tmp_path / "disp_run"
    run_dir.mkdir()
    roster = {
        "gate": {"processes": [], "vram_mb": 4096},
        "classes": {
            "fast": {
                "model": DEFAULT_MODEL_TIERS["fast_coder"].model,
                "slots": 1,
                "schema": {"type": "object", "required": ["ok"]},
            }
        },
    }
    manifest = {
        "run_id": "cov-run-1",
        "jobs": [
            {"id": "j1", "class": "fast", "prompt": "hi"},
            {"id": "j2", "class": "fast", "prompt": "hi2"},
        ],
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (run_dir / "out").mkdir()
    alos_home = tmp_path / "disp_home"
    alos_home.mkdir()
    (alos_home / "roster.json").write_text(json.dumps(roster), encoding="utf-8")
    monkeypatch.setenv("ALOS_SWARM_HOME", str(alos_home))
    assert dispatcher.main([str(run_dir), "--force"]) == 0
    assert (alos_home / "ledger.jsonl").exists()
    assert (run_dir / "summary.json").exists()

    # _probe_home_writable error path when target is a file instead of directory
    blocker = tmp_path / "blocker_file"
    blocker.write_text("x", encoding="utf-8")
    from alos.runtime import RuntimePaths

    res = _probe_home_writable(RuntimePaths(root=blocker))
    assert res["ok"] is False
    assert json.dumps(res)


def test_evaluator_approval_flag_and_dispatcher_error_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-010/FR-013: Assert requires_approval boundary, dispatcher errors & spinner OOM."""
    from alos.core.evaluator import EvaluatorNode, RiskLevel
    from alos.schemas.actions import EmailDraft, WebSearchQuery

    ev = EvaluatorNode(context=None)
    low_res = ev.evaluate_action(WebSearchQuery(query="weather"))
    assert low_res.risk_level == RiskLevel.LOW and low_res.requires_approval is False
    high_res = ev.evaluate_action(EmailDraft(to_email="a@b.com", subject="s", body="b"))
    assert high_res.risk_level == RiskLevel.HIGH and high_res.requires_approval is True

    # Dispatcher busy gate & missing manifest error
    missing_dir = tmp_path / "missing_run"
    missing_dir.mkdir()
    assert dispatcher.main([str(missing_dir)]) == 2

    run_dir = tmp_path / "busy_run"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(json.dumps({"jobs": []}), encoding="utf-8")
    monkeypatch.setattr(dispatcher, "gate", lambda *_a: "game running")
    assert dispatcher.main([str(run_dir)]) == 1

    # ModelSpinner OOM detection & restart predicate
    spinner = ModelSpinner(port=19998)
    assert spinner._is_oom_failure("CUDA out of memory") is True
    assert spinner._is_oom_failure("ok") is False
    assert spinner._needs_server_restart(DEFAULT_MODEL_TIERS["fast_coder"]) is True
    assert spinner.active_model is None
    assert spinner.managed_pids() == set()

    # is_usage_preempted & throttle recovery boundaries
    from alos.swarm.governor import (
        HysteresisConfig,
        has_throttle_recovered,
        is_throttled,
        is_usage_preempted,
    )
    from alos.swarm.sensors import TelemetrySnapshot

    cfg = HysteresisConfig()
    assert is_usage_preempted(TelemetrySnapshot(d3d_fullscreen=True), cfg) is not None
    assert (
        is_usage_preempted(TelemetrySnapshot(used_vram_mb=9000, managed_vram_mb=1000), cfg)
        is not None
    )
    assert (
        is_throttled(TelemetrySnapshot(gpu_temp_c=80.0, user_idle_seconds=600.0), cfg) is not None
    )
    assert (
        has_throttle_recovered(
            TelemetrySnapshot(gpu_temp_c=50.0, cpu_temp_c=50.0, user_idle_seconds=600.0), cfg
        )
        is True
    )

    # sandbox.require_image success & failure contracts (kills sandbox.py:226 mutant)
    import subprocess

    from alos.swarm import sandbox

    monkeypatch.setattr(
        sandbox.subprocess,
        "run",
        lambda cmd, **_kw: subprocess.CompletedProcess(cmd, 0, b"", b""),
    )
    sandbox.require_image("alos-sandbox:ok")

    monkeypatch.setattr(
        sandbox.subprocess,
        "run",
        lambda cmd, **_kw: subprocess.CompletedProcess(cmd, 1, b"", b"missing"),
    )
    with pytest.raises(sandbox.SandboxError, match="not available"):
        sandbox.require_image("alos-sandbox:missing")

    # default_prompt_executor context_length > 0 vs 0 handling (kills queue.py:597 mutant)
    import threading

    from alos.swarm.queue import LeasedJob, default_prompt_executor

    seen_bodies: list[dict[str, object] | None] = []

    def fake_ollama_call(
        self: Ollama, path: str, body: dict[str, object] | None = None, timeout: float = 10.0
    ) -> dict[str, object]:
        seen_bodies.append(body)
        if path == "/api/ps":
            return {"models": [{"name": "qwen2.5-coder:7b-instruct", "context_length": 4096}]}
        return {"response": "READY", "eval_count": 1}

    monkeypatch.setattr(Ollama, "call", fake_ollama_call)
    job = LeasedJob(
        job_id="j-ctx",
        repo_slug="alos",
        workflow_type="smoke",
        model_tier="fast_coder",
        priority=50,
        requires_merge=False,
        allow_cloud_overflow=False,
        payload={"prompt": "hi"},
        checkpoint_ns=None,
        state="leased",
        attempts=1,
        max_attempts=2,
    )
    res_exec = default_prompt_executor(job, Ollama(), threading.Event())
    assert res_exec["response"] == "READY"
    gen_body = seen_bodies[-1]
    assert isinstance(gen_body, dict) and gen_body["options"]["num_ctx"] == 4096  # type: ignore[index]  # TypedDict/object narrowing for test dict assertion
