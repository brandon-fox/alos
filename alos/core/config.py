import os
from typing import Any

from pydantic import BaseModel, Field


class ALOSConfig(BaseModel):
    """Central configuration for ALOS runtime following 12-Factor App principles
    (Factor III: Config).

    All values are read from environment variables with safe fallback defaults.
    """

    vault_dir: str = Field(default_factory=lambda: os.getenv("ALOS_VAULT_DIR", "vault"))
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

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()
