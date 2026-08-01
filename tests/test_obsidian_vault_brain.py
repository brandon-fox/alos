import os

from alos.core.context_assembler import ContextAssembler
from alos.memory.brain_synthesizer import ObsidianBrainSynthesizer
from alos.memory.obsidian_graph import ObsidianGraphEngine
from alos.memory.obsidian_vault import ObsidianVaultParser


def test_obsidian_vault_parser_frontmatter_and_wikilinks(tmp_path):
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    note_content = """---
tags:
  - brain/memory
  - project/alos
author: Alex
created: 2026-08-01
---
# Personal Knowledge Base

This is a core memory note linking to [[USER_PROFILE]] and [[PREFERENCES#Rules]].
Also see [[Delta Airlines|Delta Flights]] for travel preferences.

> [!NOTE]
> Local-first memory rule.
"""
    (vault_dir / "knowledge.md").write_text(note_content, encoding="utf-8")

    parser = ObsidianVaultParser(vault_dir=str(vault_dir))
    notes = parser.parse_all()

    assert len(notes) >= 1
    target = next(n for n in notes if n.file_name == "knowledge.md")

    assert target.frontmatter["author"] == "Alex"
    assert "brain/memory" in target.tags
    assert "project/alos" in target.tags
    assert "USER_PROFILE" in target.wiki_links
    assert "PREFERENCES" in target.wiki_links
    assert "Delta Airlines" in target.wiki_links


def test_obsidian_graph_engine_neighborhood_traversal(tmp_path):
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    (vault_dir / "NoteA.md").write_text("Links to [[NoteB]]", encoding="utf-8")
    (vault_dir / "NoteB.md").write_text("Links to [[NoteC]]", encoding="utf-8")
    (vault_dir / "NoteC.md").write_text("Core node", encoding="utf-8")

    graph = ObsidianGraphEngine(vault_dir=str(vault_dir))
    neighborhood = graph.get_neighborhood(center_note="NoteA", depth=2)

    assert "NoteA" in neighborhood.nodes
    assert "NoteB" in neighborhood.nodes
    assert "NoteC" in neighborhood.nodes


def test_obsidian_brain_synthesizer_daily_and_memory_notes(tmp_path):
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    synthesizer = ObsidianBrainSynthesizer(vault_dir=str(vault_dir))

    # Daily note creation
    daily_file = synthesizer.append_daily_note(
        date_str="2026-08-01",
        content="Refactored brain graph engine and added Obsidian vault parser.",
        tags=["alos/daily", "journal"],
    )
    assert os.path.exists(daily_file)
    daily_text = (vault_dir / "Daily Notes" / "2026-08-01.md").read_text(encoding="utf-8")
    assert "Refactored brain graph engine" in daily_text
    assert "alos/daily" in daily_text

    # Memory note creation
    mem_file = synthesizer.create_memory_note(
        title="Delta Flight Preference",
        content="Always evaluate Delta Airlines options before booking domestic flights.",
        tags=["preference", "travel"],
        wiki_links=["USER_PROFILE", "PREFERENCES"],
    )
    assert os.path.exists(mem_file)
    mem_text = (vault_dir / "Memory" / "Delta Flight Preference.md").read_text(encoding="utf-8")
    assert "[[USER_PROFILE]]" in mem_text
    assert "[[PREFERENCES]]" in mem_text


def test_context_assembler_with_obsidian_brain_graph(tmp_path):
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    (vault_dir / "USER_PROFILE.md").write_text(
        "User: Alex\nTimezone: America/New_York", encoding="utf-8"
    )
    (vault_dir / "PREFERENCES.md").write_text(
        "Rules:\n- No meetings scheduled after 5:00 PM\n- Check [[Delta Flight Preference]]",
        encoding="utf-8",
    )
    (vault_dir / "CORRECTION_LEDGER.md").write_text(
        "History:\n- Never book flights without checking Delta options first",
        encoding="utf-8",
    )

    mem_dir = vault_dir / "Memory"
    mem_dir.mkdir()
    (mem_dir / "Delta Flight Preference.md").write_text(
        "---\ntags:\n  - preference\n---\nDetailed delta booking rules.", encoding="utf-8"
    )

    assembler = ContextAssembler(vault_dir=str(vault_dir))
    context = assembler.assemble_context(user_query="Book flight to San Francisco")

    assert context.profile["User"] == "Alex"
    assert "No meetings scheduled after 5:00 PM" in context.preferences
    assert hasattr(context, "wiki_links")
    assert "Delta Flight Preference" in context.wiki_links
