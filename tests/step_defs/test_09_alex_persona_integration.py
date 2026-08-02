"""Step definitions for 09_alex_persona_integration.feature."""

from pathlib import Path
from typing import Any

from pytest_bdd import given, parsers, scenarios, then, when

from alos.core.context_assembler import ContextAssembler, ContextPayload
from alos.core.evaluator import EvaluatorNode
from alos.memory.obsidian_graph import ObsidianGraphEngine
from alos.schemas.actions import WebSearchQuery

scenarios("../features/09_alex_persona_integration.feature")


@given("user profile Alex with vault storage on local disk")
def step_user_profile_alex(tmp_path: Path, bdd_context: dict[str, Any]) -> None:
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    (vault_dir / "USER_PROFILE.md").write_text("User: Alex\nRole: Executive", encoding="utf-8")
    (vault_dir / "PREFERENCES.md").write_text("No external tracking", encoding="utf-8")
    (vault_dir / "CORRECTION_LEDGER.md").write_text("", encoding="utf-8")

    bdd_context["vault_dir"] = vault_dir


@when("ALOS evaluates user query and context payload")
def step_evaluate_query_context(bdd_context: dict[str, Any]) -> None:
    vault_dir: Path = bdd_context["vault_dir"]
    assembler = ContextAssembler(vault_dir=str(vault_dir))
    context = assembler.assemble_context(user_query="Summarize my day")
    bdd_context["context"] = context


@then("context evaluation must execute strictly locally without third-party API exposure")
def step_verify_local_execution(bdd_context: dict[str, Any]) -> None:
    context: ContextPayload = bdd_context["context"]
    assert context.profile.get("User") == "Alex"


@given(parsers.parse('CORRECTION_LEDGER note specifying "{ledger_entry}"'))
def step_ledger_entry(tmp_path: Path, bdd_context: dict[str, Any], ledger_entry: str) -> None:
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    (vault_dir / "CORRECTION_LEDGER.md").write_text(f"- {ledger_entry}", encoding="utf-8")
    bdd_context["graph_vault"] = vault_dir
    bdd_context["ledger_entry"] = ledger_entry


@given(parsers.parse("linked memory note [[{note_name}]]"))
def step_linked_memory_note(bdd_context: dict[str, Any], note_name: str) -> None:
    vault_dir: Path = bdd_context["graph_vault"]
    mem_dir = vault_dir / "Memory"
    mem_dir.mkdir(parents=True, exist_ok=True)
    (mem_dir / f"{note_name}.md").write_text(
        "Always prefer Delta airlines for flights.", encoding="utf-8"
    )
    engine = ObsidianGraphEngine(vault_dir=str(vault_dir))
    bdd_context["graph_engine"] = engine


@when("Planner generates a flight booking draft")
def step_flight_booking_draft(bdd_context: dict[str, Any]) -> None:
    context = ContextPayload(
        profile={"User": "Alex"},
        preferences=[],
        corrections=[bdd_context["ledger_entry"]],
    )
    evaluator = EvaluatorNode(context=context)

    action = WebSearchQuery(query="Book United flight to San Francisco")
    evaluation = evaluator.evaluate_action(action=action)
    bdd_context["evaluation"] = evaluation


@then("Evaluator must verify compliance against graph memory and reject non-compliant plans")
def step_verify_rejection(bdd_context: dict[str, Any]) -> None:
    evaluation = bdd_context["evaluation"]
    assert evaluation.valid is False
    assert "Never book flights without checking Delta options first" in evaluation.critique
