"""Step definitions for 08_obsidian_vault_brain.feature."""

import os
from pathlib import Path
from typing import Any

from pytest_bdd import given, scenarios, then, when

from alos.memory.brain_synthesizer import ObsidianBrainSynthesizer
from alos.memory.obsidian_graph import ObsidianGraphEngine
from alos.memory.obsidian_vault import ObsidianVaultParser

scenarios("../features/08_obsidian_vault_brain.feature")


@given("an Obsidian vault directory with a note containing frontmatter and [[WikiLinks]]")
def step_vault_with_wikilinks(tmp_path: Path, bdd_context: dict[str, Any]) -> None:
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)

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
"""
    (vault_dir / "knowledge.md").write_text(note_content, encoding="utf-8")
    bdd_context["vault_dir"] = vault_dir


@when("ObsidianVaultParser processes the note")
def step_parser_processes_note(bdd_context: dict[str, Any]) -> None:
    vault_dir: Path = bdd_context["vault_dir"]
    parser = ObsidianVaultParser(vault_dir=str(vault_dir))
    notes = parser.parse_all()
    bdd_context["parsed_notes"] = notes


@then("frontmatter tags, custom properties, and WikiLinks must be extracted cleanly")
def step_verify_extracted_metadata(bdd_context: dict[str, Any]) -> None:
    notes = bdd_context["parsed_notes"]
    assert len(notes) >= 1
    target = next(n for n in notes if n.file_name == "knowledge.md")
    assert target.frontmatter["author"] == "Alex"
    assert "brain/memory" in target.tags
    assert "USER_PROFILE" in target.wiki_links


@given("an Obsidian vault with linked notes A -> B and B -> C")
def step_vault_linked_notes(tmp_path: Path, bdd_context: dict[str, Any]) -> None:
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)

    (vault_dir / "NoteA.md").write_text("Links to [[NoteB]]", encoding="utf-8")
    (vault_dir / "NoteB.md").write_text("Links to [[NoteC]]", encoding="utf-8")
    (vault_dir / "NoteC.md").write_text("Core node", encoding="utf-8")

    bdd_context["graph_vault_dir"] = vault_dir


@when("ObsidianGraphEngine builds the graph")
def step_build_graph(bdd_context: dict[str, Any]) -> None:
    vault_dir: Path = bdd_context["graph_vault_dir"]
    engine = ObsidianGraphEngine(vault_dir=str(vault_dir))
    bdd_context["graph_engine"] = engine


@then("neighborhood resolution for A at depth 2 must return notes A, B, and C")
def step_verify_neighborhood(bdd_context: dict[str, Any]) -> None:
    engine: ObsidianGraphEngine = bdd_context["graph_engine"]
    neighborhood = engine.get_neighborhood(center_note="NoteA", depth=2)
    assert "NoteA" in neighborhood.nodes
    assert "NoteB" in neighborhood.nodes
    assert "NoteC" in neighborhood.nodes


@given("a daily journal entry request for ALOS")
def step_daily_journal_request(tmp_path: Path, bdd_context: dict[str, Any]) -> None:
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    bdd_context["synth_vault_dir"] = vault_dir


@when("ObsidianBrainSynthesizer creates or appends a daily note")
def step_synthesize_daily_note(bdd_context: dict[str, Any]) -> None:
    vault_dir: Path = bdd_context["synth_vault_dir"]
    synthesizer = ObsidianBrainSynthesizer(vault_dir=str(vault_dir))
    daily_file = synthesizer.append_daily_note(
        date_str="2026-08-01",
        content="Refactored brain graph engine.",
        tags=["alos/daily"],
    )
    bdd_context["daily_file"] = daily_file


@then("the note must be written under vault/Daily Notes/ with valid frontmatter and content")
def step_verify_daily_note(bdd_context: dict[str, Any]) -> None:
    daily_file: str = bdd_context["daily_file"]
    assert os.path.exists(daily_file)
    content = Path(daily_file).read_text(encoding="utf-8")
    assert "Refactored brain graph engine" in content
