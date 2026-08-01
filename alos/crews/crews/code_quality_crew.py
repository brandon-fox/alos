import os
from typing import Any

import yaml

from alos.crews.config import LocalLLMConfig
from alos.crews.tools.evaluator_tool import SafetyEvaluatorTool


class CodeQualityCrew:
    """Agents-as-Code crew for running static code analysis, type audits, and refactoring."""

    def __init__(
        self, config_dir: str | None = None, llm_config: LocalLLMConfig | None = None
    ) -> None:
        self.config_dir = config_dir or os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "config"
        )
        self.llm_config = llm_config or LocalLLMConfig()
        self.agents_config = self._load_yaml("agents.yaml")
        self.tasks_config = self._load_yaml("tasks.yaml")
        self.safety_tool = SafetyEvaluatorTool()

    def _load_yaml(self, filename: str) -> dict[str, Any]:
        filepath = os.path.join(self.config_dir, filename)
        if os.path.exists(filepath):
            with open(filepath, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    def run(self, target_module: str = "alos") -> dict[str, Any]:
        """Execute CodeQualityCrew audit workflow."""
        agent_data = self.agents_config.get("static_analyzer", {})
        task_data = self.tasks_config.get("audit_code_quality_task", {})

        eval_result = self.safety_tool.run(
            action_type="code_quality_audit",
            description=f"Run static analysis audit on module: {target_module}",
        )

        return {
            "status": "SUCCESS",
            "crew": "CodeQualityCrew",
            "target_module": target_module,
            "agent": agent_data.get("role", "Static Code Analysis Auditor"),
            "task": task_data.get("description", "").format(target_module=target_module),
            "safety_gate": eval_result,
            "llm": self.llm_config.to_dict(),
        }
