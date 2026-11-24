"""RED-first mocked and live tests for Hexagonal vault and graph outbound adapters."""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from alos.adapters.outbound.vault import FilesystemVaultAdapter, NetworkXGraphAdapter
from alos.application.ports.outbound import VaultRepositoryPort
from alos.application.use_cases.assemble_context import AssembleContextUseCase
from alos.domain.models.memory import GraphNeighborhood, ObsidianNote


def _enable_alos_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    """Restore propagate/disabled flags on existing alos.* loggers for deterministic caplog."""
    for name, obj in list(logging.Logger.manager.loggerDict.items()):
        if isinstance(obj, logging.Logger) and (name == "alos" or name.startswith("alos.")):
            monkeypatch.setattr(obj, "propagate", True)
            monkeypatch.setattr(obj, "disabled", False)


@pytest.mark.mocked
def test_filesystem_vault_adapter_port_use_case_and_native_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify VaultRepositoryPort compliance, alias reads, warnings, and native fallback."""
    _enable_alos_logging(monkeypatch)
    v = tmp_path / "vault"
    v.mkdir()
    (v / "USER_PROFILE.md").write_text("# H\n- User: Alex\nRole: Eng\n", encoding="utf-8")
    (v / "PREFERENCES.md").write_text("# R\n- Prefer [[Delta]]\n", encoding="utf-8")
    (v / "CORRECTION_LEDGER.md").write_text("- Never skip [[Audit]]\n", encoding="utf-8")
    (v / "bad.md").write_text("---\ntags: [broken\n---\nBody [[Solo]] #t1\n", encoding="utf-8")
    (v / "corrupt.md").write_bytes(b"\xff\xfe\x00\x00")

    adapter = FilesystemVaultAdapter(str(v))
    assert isinstance(adapter, VaultRepositoryPort)
    with caplog.at_level(logging.WARNING):
        ctx = AssembleContextUseCase(vault=adapter).execute("travel")
    assert ctx.profile == {"User": "Alex", "Role": "Eng"}
    assert ctx.preferences == ["Prefer [[Delta]]"] and ctx.corrections == ["Never skip [[Audit]]"]
    assert "Delta" in ctx.wiki_links and "Solo" in ctx.wiki_links
    assert any("unreadable" in r.message or "frontmatter" in r.message for r in caplog.records)
    assert adapter.read_list("corrupt.md") == [] and adapter.read_list("missing.md") == []
    assert FilesystemVaultAdapter(str(tmp_path / "none")).read_profile() == {}

    parsed_bad, field = adapter.parse_file(str(v / "bad.md")), "content"
    with pytest.raises(ValidationError):
        setattr(parsed_bad, field, "mutated")

    s = SimpleNamespace(
        file_name="N.md", file_path="N.md", content="ok", frontmatter={}, tags=[], wiki_links=[]
    )
    ok_n = MagicMock(parse_file=MagicMock(return_value=s), parse_all=MagicMock(return_value=[s]))
    ok_v = FilesystemVaultAdapter(str(v), use_native=True, native_parser_cls=lambda _d: ok_n)
    expected = ObsidianNote(file_name="N.md", file_path="N.md", content="ok")
    assert ok_v.parse_file("N.md") == expected and ok_v.parse_all() == [expected]

    err = RuntimeError("native fail")
    bad_n = MagicMock(parse_file=MagicMock(side_effect=err), parse_all=MagicMock(side_effect=err))
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        fb = FilesystemVaultAdapter(str(v), use_native=True, native_parser_cls=lambda _d: bad_n)
        assert isinstance(fb.parse_file(str(v / "PREFERENCES.md")), ObsidianNote)
        assert len(fb.parse_all()) >= 3
    assert len([r for r in caplog.records if "Native FastVaultParser" in r.message]) >= 2


@pytest.mark.mocked
def test_networkx_graph_adapter_mocked_native_and_warning_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify native FastGraphEngine success and structured warning fallback to NetworkX."""
    _enable_alos_logging(monkeypatch)
    v = tmp_path / "vault"
    v.mkdir()
    (v / "A.md").write_text("Link [[B]]", encoding="utf-8")
    (v / "B.md").write_text("Link [[C]]", encoding="utf-8")

    ok_g = MagicMock(get_neighborhood=MagicMock(return_value=["A", "Z"]))
    hood = NetworkXGraphAdapter(str(v), use_native=True, native_graph_cls=lambda: ok_g)
    res = hood.get_neighborhood("A", depth=1)
    assert isinstance(res, GraphNeighborhood) and res.nodes == {"A", "Z"}

    bad_g = MagicMock(get_neighborhood=MagicMock(side_effect=RuntimeError("g")))
    with caplog.at_level(logging.WARNING):
        fb = NetworkXGraphAdapter(str(v), use_native=True, native_graph_cls=lambda: bad_g)
        assert fb.get_neighborhood("A", depth=1).nodes == {"A", "B"}
    assert any("Native FastGraphEngine" in r.message for r in caplog.records)


@pytest.mark.live
def test_live_vault_synthesis_graph_traversal_and_legacy_shims(tmp_path: Path) -> None:
    """Verify live tmp_path note writes, graph hops, and alos.memory Strangler-Fig shims."""
    from alos.memory.brain_synthesizer import ObsidianBrainSynthesizer
    from alos.memory.obsidian_graph import ObsidianGraphEngine
    from alos.memory.obsidian_vault import ObsidianVaultParser

    v = tmp_path / "live_vault"
    v.mkdir()
    vault = FilesystemVaultAdapter(str(v))
    assert Path(vault.append_daily_note("2026-11-24", "Entry", tags=["alos/log"])).is_file()
    assert Path(vault.create_memory_note("Plain", "Body")).is_file()
    seed = vault.create_memory_note("Seed", "Root", tags=["c"], wiki_links=["Leaf"])
    assert Path(seed).is_file()
    (v / "Leaf.md").write_text("Leaf [[Hop2]]", encoding="utf-8")
    (v / "Hop2.md").write_text("End", encoding="utf-8")

    graph = NetworkXGraphAdapter(str(v))
    assert graph.get_neighborhood("Seed", depth=1).nodes == {"Seed", "Leaf"}
    assert graph.get_neighborhood("Seed", depth=2).nodes == {"Seed", "Leaf", "Hop2"}
    assert graph.get_neighborhood("Missing", depth=2).nodes == {"Missing"}
    assert isinstance(ObsidianVaultParser(str(v)).parse_all()[0], ObsidianNote)
    assert "Hop2" in ObsidianGraphEngine(str(v)).get_neighborhood("Seed", depth=2).nodes
    assert Path(ObsidianBrainSynthesizer(str(v)).append_daily_note("2026-11-25", "Hi")).is_file()
