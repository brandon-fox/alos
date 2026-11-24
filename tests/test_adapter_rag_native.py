"""RED-first unit tests for Wave 3 RAG and native outbound adapters (PR-10).

Spec: specs/036-hexagonal-twelve-factor-refactor/spec.md (FR-3607, FR-3611)
"""

from __future__ import annotations

from pathlib import Path

from alos.adapters.outbound.native import (
    FallbackBM25Indexer,
    NativeSafetyAcceleratorAdapter,
    get_bm25_indexer,
)
from alos.adapters.outbound.rag import BM25SpecMemoryStore, BM25VaultMemoryStore
from alos.application.ports.outbound import MemoryStorePort
from alos.domain.models.context import RAGDocument
from alos.domain.models.evaluation import RiskLevel
from alos.memory.spec_rag import SpecRAGIndexer
from alos.memory.vector_store import LocalVectorStore


def test_rag_stores_lazy_build_lsp_and_shims(tmp_path: Path) -> None:
    """Verify lazy index build, MemoryStorePort RAGDocument parity, and legacy shims."""
    vault = tmp_path / "vault"
    specs = tmp_path / "specs"
    vault.mkdir()
    specs.mkdir()
    vault_store = BM25VaultMemoryStore(str(vault))
    spec_store = BM25SpecMemoryStore(str(tmp_path))
    assert isinstance(vault_store, MemoryStorePort) and isinstance(spec_store, MemoryStorePort)
    assert vault_store.is_indexed is False and spec_store.is_indexed is False

    (vault / "travel.md").write_text("Always check Delta flights first.", encoding="utf-8")
    (vault / "other.md").write_text("Groceries list and milk.", encoding="utf-8")
    (vault / "extra.md").write_text("Daily calendar routine.", encoding="utf-8")
    (specs / "s1.md").write_text("# Safety Matrix\nGate high risk emails.", encoding="utf-8")
    (specs / "s2.md").write_text("# Notes\nUnrelated setup doc.", encoding="utf-8")
    (specs / "s3.md").write_text("# Misc\nAnother baseline item.", encoding="utf-8")

    vault_hits = vault_store.search("Delta", top_k=3)
    spec_hits = spec_store.search("Safety", top_k=3, source_filter="spec")
    assert vault_store.is_indexed is True and spec_store.is_indexed is True
    assert len(spec_store.chunks) >= 3
    assert all(isinstance(d, RAGDocument) and d.score > 0.0 for d in [*vault_hits, *spec_hits])
    assert vault_store.search("zzznomatchzzz") == []
    assert spec_store.search("zzznomatchzzz") == []
    assert vault_store.search("", top_k=1)[0].score == 0.0
    assert BM25VaultMemoryStore(str(tmp_path / "missing")).search("Delta") == []
    assert LocalVectorStore(str(vault)).search("Delta")[0]["filename"] == "travel.md"
    assert SpecRAGIndexer(str(tmp_path)).search("Safety")[0]["source_type"] == "spec"


def test_native_adapters_and_bm25_non_match_parity() -> None:
    """Verify NativeSafetyAcceleratorAdapter and FallbackBM25Indexer non-match LSP parity."""
    acc = NativeSafetyAcceleratorAdapter()
    assert acc.classify_risk("web_search") is RiskLevel.LOW
    assert acc.classify_risk("email_send") is RiskLevel.HIGH
    assert acc.classify_risk("unknown_tool") is RiskLevel.HIGH
    cal = acc.validate_calendar_preferences(
        "google_calendar_create_event",
        "2026-08-02T18:00:00",
        ["No meetings scheduled after 5:00 PM"],
    )
    corr = acc.validate_corrections("book flight", ["Always check Delta first"])
    assert cal["valid"] is False and corr["valid"] is False

    idx = get_bm25_indexer()
    fb = FallbackBM25Indexer()
    for target in (idx, fb):
        target.add_chunk("Safety", "a.md", "/a.md", "spec", "high risk approval gate")
        assert target.search("zzznomatchzzz") == []
        assert target.search("", top_k=1)[0]["score"] == 0.0
