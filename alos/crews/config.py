import os
from typing import Any


def disable_crewai_telemetry() -> None:
    """Disable all CrewAI telemetry to ensure 100% local privacy and zero cloud egress."""
    os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"
    os.environ["OTEL_SDK_DISABLED"] = "true"


# Disable telemetry immediately on module import
disable_crewai_telemetry()


class LocalLLMConfig:
    """Configuration helper for 100% local Ollama/LiteLLM execution in ALOS."""

    def __init__(
        self,
        model: str = "ollama/qwen2.5-coder:32b",
        base_url: str = "http://localhost:11434",
        fallback_model: str = "ollama/llama3.1:8b",
        is_mock: bool = False,
    ) -> None:
        self.model = model
        self.base_url = base_url
        self.fallback_model = fallback_model
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
            "telemetry_disabled": os.getenv("CREWAI_TELEMETRY_OPT_OUT") == "true",
        }
