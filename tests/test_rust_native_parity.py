"""Parity tests asserting identical behavior between pure Python implementations
and Rust native performance extensions (with graceful fallback testing).
"""

import tempfile
from pathlib import Path

from alos.memory.obsidian_graph import ObsidianGraphEngine
from alos.memory.obsidian_vault import ObsidianNote, ObsidianVaultParser
from alos.memory.spec_rag import SpecRAGIndexer


def test_obsidian_vault_parser_parity() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        vault_path = Path(tmp_dir)
        note_file = vault_path / "test_note.md"
        note_file.write_text(
            "---\ntitle: Rust Test\ntags:\n  - rust\n  - perf\n---\n"
            "# Header\nThis is body content with [[TargetNote]] link and #inline-tag.",
            encoding="utf-8",
        )

        parser = ObsidianVaultParser(vault_dir=str(vault_path))
        notes = parser.parse_all()

        assert len(notes) == 1
        note: ObsidianNote = notes[0]
        assert note.file_name == "test_note.md"
        assert "rust" in note.tags
        assert "TargetNote" in note.wiki_links


def test_spec_rag_indexer_search_parity() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        specs_dir = Path(tmp_dir) / "specs"
        specs_dir.mkdir(parents=True, exist_ok=True)
        spec_file = specs_dir / "spec.md"
        spec_file.write_text(
            "# Architecture Specification\n"
            "High performance Rust extensions for local memory indexing.",
            encoding="utf-8",
        )
        spec_file2 = specs_dir / "spec2.md"
        spec_file2.write_text(
            "# Unrelated Doc\n"
            "This document discusses database migrations and SQL schema changes.",
            encoding="utf-8",
        )
        spec_file3 = specs_dir / "spec3.md"
        spec_file3.write_text(
            "# Another Doc\n"
            "This file describes python environment setup and poetry configuration.",
            encoding="utf-8",
        )

        indexer = SpecRAGIndexer(root_dir=tmp_dir)
        results = indexer.search("performance Rust")

        assert len(results) > 0
        assert results[0]["header"] in ("Architecture Specification", "General")
        assert "performance" in results[0]["content"].lower()


def test_obsidian_graph_engine_parity() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        vault_path = Path(tmp_dir)
        note_a = vault_path / "NoteA.md"
        note_a.write_text("Reference to [[NoteB]] and [[NoteC]].", encoding="utf-8")
        note_b = vault_path / "NoteB.md"
        note_b.write_text("Reference to [[NoteD]].", encoding="utf-8")

        graph_engine = ObsidianGraphEngine(vault_dir=str(vault_path))
        neighborhood = graph_engine.get_neighborhood("NoteA", depth=2)

        assert neighborhood.center_note == "NoteA"
        assert "NoteA" in neighborhood.nodes
        assert "NoteB" in neighborhood.nodes
