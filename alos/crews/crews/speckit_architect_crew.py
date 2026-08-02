"""CrewAI agent crew for SpecKit architecture specification generation."""

import os
from typing import Any

import yaml
from pydantic import BaseModel

from alos.crews.config import LocalLLMConfig
from alos.crews.tools.evaluator_tool import SafetyEvaluatorTool
from alos.crews.tools.obsidian_tool import ObsidianVaultTool


class CrewAgentSpec(BaseModel):
    """Specification model for a CrewAI agent role and goal."""

    role: str
    goal: str
    backstory: str


class CrewTaskSpec(BaseModel):
    """Specification model for a CrewAI task definition."""

    description: str
    expected_output: str
    agent: str


class SpecKitArchitectCrew:
    """Agents-as-Code crew for generating SpecKit feature directories and specifications."""

    def __init__(
        self, config_dir: str | None = None, llm_config: LocalLLMConfig | None = None
    ) -> None:
        self.config_dir = config_dir or os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "config"
        )
        self.llm_config = llm_config or LocalLLMConfig()
        self.agents_config = self._load_yaml("agents.yaml")
        self.tasks_config = self._load_yaml("tasks.yaml")
        self.vault_tool = ObsidianVaultTool()
        self.safety_tool = SafetyEvaluatorTool()

    def _load_yaml(self, filename: str) -> dict[str, Any]:
        filepath = os.path.join(self.config_dir, filename)
        if os.path.exists(filepath):
            with open(filepath, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    def get_agent_spec(self, name: str) -> CrewAgentSpec:
        """Parse agent specification for named agent configuration."""
        data = self.agents_config.get(name, {})
        role = str(data.get("role", name.replace("_", " ").title())).strip()
        goal = str(data.get("goal", f"Achieve goals for {name}")).strip()
        backstory = str(data.get("backstory", f"Backstory for {name}")).strip()
        return CrewAgentSpec(role=role, goal=goal, backstory=backstory)

    def get_task_spec(self, name: str) -> CrewTaskSpec:
        """Parse task specification for named task configuration."""
        data = self.tasks_config.get(name, {})
        desc = str(data.get("description", f"Execute task {name}")).strip()
        out = str(data.get("expected_output", "Task completion output")).strip()
        agent = str(data.get("agent", "spec_architect")).strip()
        return CrewTaskSpec(description=desc, expected_output=out, agent=agent)

    def run(self, goal: str) -> dict[str, Any]:
        """Execute SpecKit creation workflow (supports mock / test execution mode)."""
        spec_agent = self.get_agent_spec("spec_architect")
        plan_agent = self.get_agent_spec("tech_lead")

        spec_task = self.get_task_spec("draft_spec_task")
        plan_task = self.get_task_spec("draft_plan_task")

        # Evaluate safety gate
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
