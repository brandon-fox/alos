"""Integration testing for Alex Persona behavior, local-first memory graph resolution,
Safety Matrix evaluation, and audit trail logging.
"""

from alos.core.context_assembler import ContextAssembler
from alos.core.evaluator import EvaluatorNode, RiskLevel
from alos.memory.brain_synthesizer import ObsidianBrainSynthesizer
from alos.memory.obsidian_graph import ObsidianGraphEngine
from alos.schemas.actions import EmailDraft, TodoistTaskCreate


def test_alex_persona_privacy_and_local_memory_assembly(tmp_path):
    """BDD Scenario: Honor local-first privacy constraint for Alex persona"""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    (vault_dir / "USER_PROFILE.md").write_text("User: Alex\nRole: Tech Executive", encoding="utf-8")
    (vault_dir / "PREFERENCES.md").write_text(
        "Rules:\n- No meetings scheduled after 5:00 PM", encoding="utf-8"
    )
    (vault_dir / "CORRECTION_LEDGER.md").write_text(
        "History:\n- Never book flights without checking Delta options first",
        encoding="utf-8",
    )

    assembler = ContextAssembler(vault_dir=str(vault_dir))
    context = assembler.assemble_context(user_query="Plan remote worker schedule")

    assert context.profile["User"] == "Alex"
    assert context.profile["Role"] == "Tech Executive"
    assert "No meetings scheduled after 5:00 PM" in context.preferences
    assert "Never book flights without checking Delta options first" in context.corrections


def test_alex_persona_graph_memory_self_correction(tmp_path):
    """BDD Scenario: Self-correct based on past ledger entries and Obsidian graph memory"""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    synthesizer = ObsidianBrainSynthesizer(vault_dir=str(vault_dir))
    synthesizer.create_memory_note(
        title="Executive Travel Rules",
        content="Always check Delta flights first. Link to [[USER_PROFILE]].",
        tags=["preference", "travel"],
        wiki_links=["USER_PROFILE", "PREFERENCES"],
    )

    (vault_dir / "USER_PROFILE.md").write_text("User: Alex\nRole: Executive", encoding="utf-8")
    (vault_dir / "PREFERENCES.md").write_text("Rules:\n- Prefer Delta Airlines", encoding="utf-8")
    (vault_dir / "CORRECTION_LEDGER.md").write_text(
        "History:\n- Never book United without checking Delta", encoding="utf-8"
    )

    graph = ObsidianGraphEngine(vault_dir=str(vault_dir))
    neighborhood = graph.get_neighborhood(center_note="Executive Travel Rules", depth=2)

    assert "Executive Travel Rules" in neighborhood.nodes
    assert "USER_PROFILE" in neighborhood.nodes

    assembler = ContextAssembler(vault_dir=str(vault_dir))
    context = assembler.assemble_context(user_query="Book flight to San Francisco")

    evaluator = EvaluatorNode(context=context)

    medium_action = TodoistTaskCreate(title="Draft SFO Trip Itinerary")
    assert evaluator.classify_risk(medium_action) == RiskLevel.MEDIUM

    high_action = EmailDraft(
        to_email="travel@agent.com", subject="Draft SFO Trip", body="Draft itinerary"
    )
    assert evaluator.classify_risk(high_action) == RiskLevel.HIGH
