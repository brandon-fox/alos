# Spec 08 — Obsidian Vault Brain Integration

## User Story
As an ALOS autonomous agent, I need a local-first Obsidian Vault Brain engine to parse markdown frontmatter, extract WikiLinks, resolve knowledge graphs, and perform schema-validated note synthesis, so that my long-term memory, daily journal, user profile, and personal preferences remain unified, local, and graph-connected.

## Acceptance Criteria
1. **Markdown Frontmatter & Tag Parsing**: The parser MUST extract YAML frontmatter (`tags`, `aliases`, `created`, custom metadata), inline `#tags`, callout blocks, and key-value properties.
2. **WikiLinks & Knowledge Graph Extraction**: The graph engine MUST parse Obsidian WikiLinks (`[[Note Title]]`, `[[Note Title#Header]]`, `[[Note Title|Alias]]`) and construct a bi-directional graph (`nodes`, `forward_links`, `backlinks`).
3. **Graph Neighborhood Traversal**: Context assembly MUST support 1-hop and 2-hop graph neighborhood expansion to surface related memory notes.
4. **Schema-Validated Note Synthesis**: Synthesizing new notes (e.g. `vault/Daily Notes/YYYY-MM-DD.md` or `vault/Memory/<slug>.md`) MUST be schema-validated and adhere to Safety Matrix classifications (LOW for read/graph, MEDIUM for write/append, HIGH for delete).
5. **Zero Cloud Dependency**: Vault operations MUST execute 100% locally on Markdown files on disk.

## Requirements
- **FR-08-01**: `ObsidianVaultParser` parses frontmatter, tags, callouts, and WikiLinks from markdown notes.
- **FR-08-02**: `ObsidianGraphEngine` builds bi-directional link graph and provides `get_neighborhood(note_name, depth)` traversal.
- **FR-08-03**: `ObsidianBrainSynthesizer` provides safe creation and append operations for daily notes, conceptual memory notes, and core ledgers (`USER_PROFILE.md`, `PREFERENCES.md`, `CORRECTION_LEDGER.md`).
- **FR-08-04**: `ContextAssembler` incorporates graph-linked vault context and wiki links into `ContextPayload`.
- **FR-08-05**: `SpecRAGIndexer` indexes WikiLinks and frontmatter tags into RAG search chunks.
