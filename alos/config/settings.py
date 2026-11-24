"""Twelve-Factor Factor III environment settings root for ALOS runtime.

Spec: specs/036-hexagonal-twelve-factor-refactor/spec.md (FR-3602, SC-002)
ADRs: docs/adr/0021, docs/adr/0022
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def _f(field_name: str, default: Any = None, env_name: str | None = None) -> Any:
    return Field(
        default=default, validation_alias=AliasChoices(env_name or field_name.upper(), field_name)
    )


class ALOSSettings(BaseSettings):
    """Centralized Twelve-Factor configuration loaded dynamically from env and .env.

    Zero import-time ``os.environ`` reads or mutations occur; all environment and
    ``.env`` resolution executes strictly at instantiation time.
    """

    model_config = SettingsConfigDict(
        env_prefix="ALOS_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    alos_home: str | None = _f("alos_home", None, "ALOS_HOME")
    swarm_home: str | None = None
    queue_db_url: str | None = None
    swarm_ollama_host: str | None = _f("swarm_ollama_host", None, "ALOS_SWARM_OLLAMA")
    vault_dir: str = "vault"
    workflows_dir: str = "workflows"
    audit_log_path: str | None = None
    decision_log_path: str | None = None
    mock_mode: bool = True
    telemetry_enabled: bool = True
    telemetry_log_path: str | None = None
    observability_host: str = "127.0.0.1"
    observability_port: int = 9464
    latency_slo_ms: float = 2000.0
    error_rate_threshold: float = 0.25
    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "json"
    database_url: str = _f(
        "database_url", "postgresql+psycopg://postgres:postgres@localhost:5432/n8n"
    )
    redis_host: str = _f("redis_host", "localhost")
    redis_port: int = _f("redis_port", 6379)
    n8n_base_url: str = _f("n8n_base_url", "http://localhost:5678")
    n8n_port: int = _f("n8n_port", 5678)
    n8n_encryption_key: SecretStr | None = _f("n8n_encryption_key")
    ollama_base_url: str = _f("ollama_base_url", "http://localhost:11434")
    ollama_model: str = _f("ollama_model", "ollama/qwen2.5-coder:32b")
    ollama_fallback_model: str = _f("ollama_fallback_model", "ollama/llama3.1:8b")
    crewai_telemetry_opt_out: bool = _f("crewai_telemetry_opt_out", False)
    openai_api_key: SecretStr | None = _f("openai_api_key")
    anthropic_api_key: SecretStr | None = _f("anthropic_api_key")
    cloudflare_tunnel_token: SecretStr | None = _f("cloudflare_tunnel_token")

    def to_dict(self) -> dict[str, Any]:
        """Serialize settings into a plain dictionary (secrets remain SecretStr)."""
        return self.model_dump()
