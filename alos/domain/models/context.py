"""Ring 1 pure domain context and RAG retrieval value objects (ADR-0022, FR-3603/3607)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class UserProfile(BaseModel):
    """Immutable domain representation of the local ALOS user profile."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    username: str
    role: str = ""
    timezone: str = "UTC"
    preferences: dict[str, Any] = Field(default_factory=dict)


class RAGDocument(BaseModel):
    """Immutable normalized retrieval document shared by vector and spec RAG ports."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    file_name: str
    file_path: str
    content: str
    score: float = Field(default=0.0, ge=0.0)
    header: str = ""
    source_type: str = "general"


class ContextPayload(BaseModel):
    """Immutable container payload for aggregated profile, rules, and RAG context."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    profile: dict[str, Any] = Field(default_factory=dict)
    preferences: list[str] = Field(default_factory=list)
    corrections: list[str] = Field(default_factory=list)
    rag_docs: list[RAGDocument] = Field(default_factory=list)
    wiki_links: list[str] = Field(default_factory=list)
