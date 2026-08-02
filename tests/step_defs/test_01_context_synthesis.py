"""Step definitions for 01_context_synthesis.feature."""

from pathlib import Path
from typing import Any

from pytest_bdd import given, parsers, scenarios, then, when

from alos.core.context_assembler import ContextAssembler

scenarios("../features/01_context_synthesis.feature")


@given(parsers.parse('a local vault containing "{file1}", "{file2}", and "{file3}"'))
def step_local_vault(
    tmp_path: Path, bdd_context: dict[str, Any], file1: str, file2: str, file3: str
) -> None:
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)

    f1 = vault_dir / file1
    if not f1.exists():
        f1.write_text("User: Alex\nTimezone: America/New_York", encoding="utf-8")

    f2 = vault_dir / file2
    if not f2.exists():
        f2.write_text("Rules:\n", encoding="utf-8")

    f3 = vault_dir / file3
    if not f3.exists():
        f3.write_text("History:\n", encoding="utf-8")

    bdd_context["vault_dir"] = vault_dir


@given(parsers.parse('"{filename}" contains rule "{rule_text}"'))
def step_file_contains_rule(bdd_context: dict[str, Any], filename: str, rule_text: str) -> None:
    vault_dir: Path = bdd_context["vault_dir"]
    target_file = vault_dir / filename
    current_content = target_file.read_text(encoding="utf-8")
    target_file.write_text(f"{current_content}\n- {rule_text}", encoding="utf-8")


@given(parsers.parse('"{filename}" contains entry "{entry_text}"'))
def step_file_contains_entry(bdd_context: dict[str, Any], filename: str, entry_text: str) -> None:
    vault_dir: Path = bdd_context["vault_dir"]
    target_file = vault_dir / filename
    current_content = target_file.read_text(encoding="utf-8")
    target_file.write_text(f"{current_content}\n- {entry_text}", encoding="utf-8")


@when(parsers.parse('Alex submits a task request "{user_query}"'))
def step_alex_submits_task(bdd_context: dict[str, Any], user_query: str) -> None:
    vault_dir: Path = bdd_context["vault_dir"]
    assembler = ContextAssembler(vault_dir=str(vault_dir))
    context = assembler.assemble_context(user_query=user_query)
    bdd_context["context"] = context


@then("ALOS Context Assembler synthesizes a context payload")
def step_context_synthesized(bdd_context: dict[str, Any]) -> None:
    assert bdd_context.get("context") is not None


@then(parsers.parse('the context payload includes the preference "{pref}"'))
def step_context_includes_pref(bdd_context: dict[str, Any], pref: str) -> None:
    context = bdd_context["context"]
    assert any(pref in p for p in context.preferences)


@then(parsers.parse('the context payload includes the past correction "{corr}"'))
def step_context_includes_corr(bdd_context: dict[str, Any], corr: str) -> None:
    context = bdd_context["context"]
    assert any(corr in c for c in context.corrections)
