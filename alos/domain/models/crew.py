"""Pure domain specification models for CrewAI agent and task definitions.

Ring 1 (Pure Domain): stdlib + pydantic only; decoupled from YAML and LLM I/O.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CrewAgentSpec(BaseModel):
    """Immutable specification model for a CrewAI agent role, goal, and backstory."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    role: str
    goal: str
    backstory: str


class CrewTaskSpec(BaseModel):
    """Immutable specification model for a CrewAI task definition."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    description: str
    expected_output: str
    agent: str
