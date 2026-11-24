"""Ring 2 pure crew specification models and injected YAML-free config loader."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict


class CrewAgentSpec(BaseModel):
    """Immutable specification model for a CrewAI agent role and goal."""

    model_config = ConfigDict(frozen=True)

    role: str
    goal: str
    backstory: str


class CrewTaskSpec(BaseModel):
    """Immutable specification model for a CrewAI task definition."""

    model_config = ConfigDict(frozen=True)

    description: str
    expected_output: str
    agent: str


class CrewConfigLoader:
    """Shared injected crew spec loader eliminating duplicate _load_yaml (DRY/DIP)."""

    def __init__(self, config_dir: str | Path, parser: Callable[[str], Any]) -> None:
        self.config_dir = Path(config_dir)
        self.parser = parser

    def load(self, filename: str) -> dict[str, Any]:
        """Load and parse filename under config_dir via the injected parser callable."""
        filepath = self.config_dir / filename
        if filepath.exists():
            parsed = self.parser(filepath.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                return parsed
        return {}

    def get_agent_spec(self, agents_config: dict[str, Any], name: str) -> CrewAgentSpec:
        """Extract a typed CrewAgentSpec from parsed agents configuration."""
        data = agents_config.get(name, {})
        role = str(data.get("role", name.replace("_", " ").title())).strip()
        goal = str(data.get("goal", f"Achieve goals for {name}")).strip()
        backstory = str(data.get("backstory", f"Backstory for {name}")).strip()
        return CrewAgentSpec(role=role, goal=goal, backstory=backstory)

    def get_task_spec(self, tasks_config: dict[str, Any], name: str) -> CrewTaskSpec:
        """Extract a typed CrewTaskSpec from parsed tasks configuration."""
        data = tasks_config.get(name, {})
        desc = str(data.get("description", f"Execute task {name}")).strip()
        out = str(data.get("expected_output", "Task completion output")).strip()
        agent = str(data.get("agent", "spec_architect")).strip()
        return CrewTaskSpec(description=desc, expected_output=out, agent=agent)
