"""Pure domain models for external workflow automation execution responses.

Ring 1 (Pure Domain): stdlib + pydantic only (Constitution Article I).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class N8nExecutionResponse(BaseModel):
    """Immutable execution or polling response returned by n8n workflow ports."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status_code: int
    data: dict[str, Any] = Field(default_factory=dict)
    execution_id: str | None = None
    error: str | None = None
