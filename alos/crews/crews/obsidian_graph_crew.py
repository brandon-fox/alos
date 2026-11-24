"""CrewAI agent crew for synthesizing Obsidian vault notes and knowledge graphs."""

from typing import Any

from alos.application.use_cases.crews import CrewConfigLoader
from alos.crews.config import LocalLLMConfig, build_crew_config_loader
from alos.crews.tools.evaluator_tool import SafetyEvaluatorTool
from alos.crews.tools.obsidian_tool import ObsidianVaultTool


class ObsidianGraphSynthesizerCrew:
    """Agents-as-Code crew for mining Obsidian daily notes and updating knowledge graph links."""

    def __init__(
        self,
        config_dir: str | None = None,
        llm_config: LocalLLMConfig | None = None,
        spec_loader: CrewConfigLoader | None = None,
    ) -> None:
        self._spec_loader = spec_loader or build_crew_config_loader(config_dir)
        self.config_dir = str(self._spec_loader.config_dir)
        self.llm_config = llm_config or LocalLLMConfig()
        self.agents_config = self._load_yaml("agents.yaml")
        self.tasks_config = self._load_yaml("tasks.yaml")
        self.vault_tool = ObsidianVaultTool()
        self.safety_tool = SafetyEvaluatorTool()

    def _load_yaml(self, filename: str) -> dict[str, Any]:
        return self._spec_loader.load(filename)

    def run(self, vault_dir: str = "vault") -> dict[str, Any]:
        """Execute ObsidianGraphSynthesizerCrew workflow."""
        agent_data = self.agents_config.get("journal_miner", {})
        task_data = self.tasks_config.get("synthesize_obsidian_notes_task", {})

        eval_result = self.safety_tool.run(
            action_type="vault_update_note",
            description=f"Synthesize notes in vault directory: {vault_dir}",
        )

        return {
            "status": "SUCCESS",
            "crew": "ObsidianGraphSynthesizerCrew",
            "vault_dir": vault_dir,
            "agent": agent_data.get("role", "Obsidian Journal Mining Specialist"),
            "task": task_data.get("description", "").format(vault_dir=vault_dir),
            "safety_gate": eval_result,
            "llm": self.llm_config.to_dict(),
        }
