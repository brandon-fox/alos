"""CrewAI agent crew for code quality, static analysis, and refactoring audits."""

from typing import Any

from alos.application.use_cases.crews import CrewConfigLoader
from alos.crews.config import LocalLLMConfig, build_crew_config_loader
from alos.crews.tools.evaluator_tool import SafetyEvaluatorTool


class CodeQualityCrew:
    """Agents-as-Code crew for running static code analysis, type audits, and refactoring."""

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
        self.safety_tool = SafetyEvaluatorTool()

    def _load_yaml(self, filename: str) -> dict[str, Any]:
        return self._spec_loader.load(filename)

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
