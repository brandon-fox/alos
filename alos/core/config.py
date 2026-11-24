"""Configuration management and settings models for ALOS runtime."""

import os
from typing import Any

from pydantic import BaseModel, Field


class ALOSConfig(BaseModel):
    """Central configuration for ALOS runtime following 12-Factor App principles
    (Factor III: Config).

    All values are read from environment variables with safe fallback defaults.
    """

    vault_dir: str = Field(default_factory=lambda: os.getenv("ALOS_VAULT_DIR", "vault"))
    workflows_dir: str = Field(default_factory=lambda: os.getenv("ALOS_WORKFLOWS_DIR", "workflows"))
    audit_log_path: str | None = Field(default_factory=lambda: os.getenv("ALOS_AUDIT_LOG_PATH"))
    decision_log_path: str | None = Field(
        default_factory=lambda: os.getenv("ALOS_DECISION_LOG_PATH")
    )
    mock_mode: bool = Field(
        default_factory=lambda: os.getenv("ALOS_MOCK_MODE", "true").lower() in ("true", "1", "yes")
    )
    database_url: str = Field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/n8n"
        )
    )
    telemetry_enabled: bool = Field(
        default_factory=lambda: (
            os.getenv("ALOS_TELEMETRY_ENABLED", "true").lower() in ("true", "1", "yes")
        )
    )
    telemetry_log_path: str | None = Field(
        default_factory=lambda: os.getenv("ALOS_TELEMETRY_LOG_PATH")
    )
    observability_host: str = Field(
        default_factory=lambda: os.getenv("ALOS_OBSERVABILITY_HOST", "127.0.0.1")
    )
    observability_port: int = Field(
        default_factory=lambda: int(os.getenv("ALOS_OBSERVABILITY_PORT", "9464"))
    )
    latency_slo_ms: float = Field(
        default_factory=lambda: float(os.getenv("ALOS_LATENCY_SLO_MS", "2000.0"))
    )
    error_rate_threshold: float = Field(
        default_factory=lambda: float(os.getenv("ALOS_ERROR_RATE_THRESHOLD", "0.25"))
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration model to dictionary representation."""
        return self.model_dump()
