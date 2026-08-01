import os

from alos.crews.config import LocalLLMConfig
from alos.crews.crews.code_quality_crew import CodeQualityCrew
from alos.crews.crews.obsidian_graph_crew import ObsidianGraphSynthesizerCrew
from alos.crews.crews.speckit_architect_crew import SpecKitArchitectCrew
from alos.crews.tools.evaluator_tool import SafetyEvaluatorTool
from alos.crews.tools.mcp_bridge_tool import MCPGatewayTool
from alos.crews.tools.n8n_tool import N8nWorkflowTool
from alos.crews.tools.obsidian_tool import ObsidianVaultTool


def test_localllmconfig_telemetry_disabled():
    """Verify CREWAI_TELEMETRY_OPT_OUT environment variable is set."""
    config = LocalLLMConfig(is_mock=True)
    kwargs = config.get_llm_kwargs()

    assert kwargs["model"] == "ollama/qwen2.5-coder:32b"
    assert kwargs["base_url"] == "http://localhost:11434"
    assert os.getenv("CREWAI_TELEMETRY_OPT_OUT") == "true"


def test_obsidian_vault_tool(tmp_path):
    """Verify ObsidianVaultTool reads vault note files."""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    note_file = vault_dir / "USER_PROFILE.md"
    note_file.write_text(
        "---\ntags: [user, profile]\n---\n# User Profile\nUser prefers local execution.",
        encoding="utf-8",
    )

    tool = ObsidianVaultTool(vault_dir=str(vault_dir))
    output = tool.run(file_name="USER_PROFILE.md", vault_dir=str(vault_dir))

    assert "USER_PROFILE.md" in output
    assert "User prefers local execution" in output


def test_safety_evaluator_tool():
    """Verify SafetyEvaluatorTool evaluates actions against ALOS Safety Matrix."""
    tool = SafetyEvaluatorTool()
    output = tool.run(action_type="email_send", description="Send automated email")

    assert "Evaluation Output" in output
    assert "Risk Level: HIGH" in output
    assert "Requires Human Approval: True" in output


def test_mcp_bridge_tool():
    """Verify MCPGatewayTool executes registered tool handlers."""
    tool = MCPGatewayTool()
    output = tool.run(tool_name="web_search", payload={"query": "ALOS local RAG"})

    assert "web_search" in output
    assert "SUCCESS" in output


def test_n8n_workflow_tool():
    """Verify N8nWorkflowTool triggers n8n workflow mock."""
    tool = N8nWorkflowTool(mock_mode=True)
    output = tool.run(
        workflow_id="wf-human-approval-gate",
        payload={"task_id": "123", "action_type": "vault_update_note", "risk_level": "HIGH"},
    )

    assert "n8n Success" in output
    assert "wf-human-approval-gate" in output


def test_speckit_architect_crew():
    """Verify SpecKitArchitectCrew execution and safety gate checks."""
    crew = SpecKitArchitectCrew(llm_config=LocalLLMConfig(is_mock=True))
    res = crew.run(goal="Test Feature Orchestration")

    assert res["status"] == "SUCCESS"
    assert res["crew"] == "SpecKitArchitectCrew"
    assert "Spec Architect" in res["agents"]
    assert "Safety_gate" in [k.capitalize() for k in res]


def test_code_quality_crew():
    """Verify CodeQualityCrew execution."""
    crew = CodeQualityCrew(llm_config=LocalLLMConfig(is_mock=True))
    res = crew.run(target_module="alos")

    assert res["status"] == "SUCCESS"
    assert res["crew"] == "CodeQualityCrew"
    assert res["target_module"] == "alos"


def test_obsidian_graph_crew():
    """Verify ObsidianGraphSynthesizerCrew execution."""
    crew = ObsidianGraphSynthesizerCrew(llm_config=LocalLLMConfig(is_mock=True))
    res = crew.run(vault_dir="vault")

    assert res["status"] == "SUCCESS"
    assert res["crew"] == "ObsidianGraphSynthesizerCrew"
