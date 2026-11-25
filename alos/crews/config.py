"""CrewAI local LLM configuration and runtime-scoped privacy telemetry control."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from alos.application.use_cases.crews import CrewConfigLoader
from alos.config.settings import ALOSSettings


def build_crew_config_loader(config_dir: str | Path | None = None) -> CrewConfigLoader:
    """Build a CrewConfigLoader wired to PyYAML safe_load for default crew configs."""
    resolved = Path(config_dir) if config_dir else Path(__file__).resolve().parent / "config"
    return CrewConfigLoader(config_dir=resolved, parser=yaml.safe_load)


def disable_crewai_telemetry() -> None:
    """Disable all CrewAI telemetry to ensure 100% local privacy and zero cloud egress."""
    os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"
    os.environ["OTEL_SDK_DISABLED"] = "true"


class LocalLLMConfig:
    """Configuration helper for 100% local Ollama/LiteLLM execution in ALOS."""

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        fallback_model: str | None = None,
        is_mock: bool = False,
    ) -> None:
        # Enforce Factor III: opt out of CrewAI telemetry at instantiation, never on import.
        disable_crewai_telemetry()
        settings = ALOSSettings()
        self.model = model or settings.ollama_model
        self.base_url = base_url or settings.ollama_base_url
        self.fallback_model = fallback_model or settings.ollama_fallback_model
        self.is_mock = is_mock

    def get_llm_kwargs(self) -> dict[str, Any]:
        """Return keyword arguments for instantiating a CrewAI LLM instance."""
        return {
            "model": self.model,
            "base_url": self.base_url,
            "temperature": 0.1,
        }

    def to_dict(self) -> dict[str, Any]:
        """Return dict representation of LLM configuration."""
        return {
            "model": self.model,
            "base_url": self.base_url,
            "fallback_model": self.fallback_model,
            "is_mock": self.is_mock,
            "telemetry_disabled": ALOSSettings().crewai_telemetry_opt_out,
        }
