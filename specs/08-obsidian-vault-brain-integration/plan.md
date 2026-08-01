# Plan 08 — Obsidian Vault Brain Engine Architecture

## Component Overview
This feature introduces an integrated Obsidian Vault Brain Engine to ALOS:
1. `ObsidianVaultParser` (`alos/memory/obsidian_vault.py`): Extracts YAML frontmatter, tags, callouts, and WikiLinks.
2. `ObsidianGraphEngine` (`alos/memory/obsidian_graph.py`): Builds in-memory bi-directional graph structure (`nodes`, `forward_links`, `backlinks`) and neighborhood resolution.
3. `ObsidianBrainSynthesizer` (`alos/memory/brain_synthesizer.py`): Schema-validated creation/append of daily notes and memory nodes.
4. `ContextAssembler` Integration (`alos/core/context_assembler.py`): Enhances context payload with graph links and neighborhood context.

## Data Schema & Models
```python
class ObsidianNote(BaseModel):
    file_path: str
    file_name: str
    title: str
    frontmatter: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    wiki_links: list[str] = Field(default_factory=list)
    content: str

class KnowledgeGraphNeighborhood(BaseModel):
    center_note: str
    nodes: list[str] = Field(default_factory=list)
    edges: list[tuple[str, str]] = Field(default_factory=list)
```

## System Integration
- `SpecRAGIndexer` is extended to index frontmatter tags and WikiLinks.
- Safety Matrix classifies read/graph operations as LOW risk, note creation/appending as MEDIUM risk, note deletion as HIGH risk.
