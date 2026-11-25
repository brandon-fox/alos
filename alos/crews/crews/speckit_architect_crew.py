"""CrewAI agent crew for SpecKit architecture specification generation."""

from typing import Any

from alos.application.use_cases.crews import CrewAgentSpec, CrewConfigLoader, CrewTaskSpec
from alos.crews.config import LocalLLMConfig, build_crew_config_loader
from alos.crews.tools.evaluator_tool import SafetyEvaluatorTool
from alos.crews.tools.obsidian_tool import ObsidianVaultTool

__all__ = ["CrewAgentSpec", "CrewTaskSpec", "SpecKitArchitectCrew"]


class SpecKitArchitectCrew:
    """Agents-as-Code crew for generating SpecKit feature directories and specifications."""

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

    def get_agent_spec(self, name: str) -> CrewAgentSpec:
        """Parse agent specification for named agent configuration."""
        return self._spec_loader.get_agent_spec(self.agents_config, name)

    def get_task_spec(self, name: str) -> CrewTaskSpec:
        """Parse task specification for named task configuration."""
        return self._spec_loader.get_task_spec(self.tasks_config, name)

    def run(self, goal: str) -> dict[str, Any]:
        """Execute SpecKit creation workflow (supports mock / test execution mode)."""
        spec_agent = self.get_agent_spec("spec_architect")
        plan_agent = self.get_agent_spec("tech_lead")
        spec_task = self.get_task_spec("draft_spec_task")
        plan_task = self.get_task_spec("draft_plan_task")

        eval_result = self.safety_tool.run(
            action_type="vault_update_note",
            description=f"Create SpecKit feature directory for goal: {goal}",
        )

        return {
            "status": "SUCCESS",
            "crew": "SpecKitArchitectCrew",
            "goal": goal,
            "agents": [spec_agent.role, plan_agent.role],
            "tasks": [
                spec_task.description.format(goal=goal),
                plan_task.description.format(goal=goal),
            ],
            "safety_gate": eval_result,
            "llm": self.llm_config.to_dict(),
        }
