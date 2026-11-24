"""Ring 1 pure domain Obsidian vault and specification RAG chunk models (ADR-0022)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ObsidianNote(BaseModel):
    """Immutable domain representation of an Obsidian vault Markdown note."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    file_name: str
    file_path: str
    content: str
    frontmatter: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    wiki_links: list[str] = Field(default_factory=list)


class GraphNeighborhood(BaseModel):
    """Immutable graph neighborhood container surrounding a center Obsidian note."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    center_note: str
    nodes: set[str] = Field(default_factory=set)


class SpecChunk(BaseModel):
    """Immutable chunk of specification or Markdown document with header metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    file_path: str
    file_name: str
    header: str
    content: str
    source_type: str
