---
name: obsidian-brain-memory
description: Automated skill for managing, parsing, and synthesizing long-term memory notes and knowledge graphs in the local Obsidian Vault.
---

# Obsidian Brain Memory Skill

This skill governs interaction with the ALOS Obsidian Vault (`vault/`) as the primary local-first brain engine.

## Key Capabilities

1. **Vault Parsing (`ObsidianVaultParser`)**:
   - Recursively reads markdown notes across `vault/`.
   - Extracts YAML frontmatter (`tags`, `aliases`, custom keys), inline `#tags`, callout blocks, and `[[WikiLinks]]`.

2. **Graph Neighborhood Traversal (`ObsidianGraphEngine`)**:
   - Builds bi-directional knowledge graphs connecting notes via WikiLinks.
   - Resolves 1-hop and 2-hop neighborhood expansion (`get_neighborhood(center_note, depth)`).

3. **Brain Note Synthesis (`ObsidianBrainSynthesizer`)**:
   - Creates daily journal notes in `vault/Daily Notes/YYYY-MM-DD.md`.
   - Creates conceptual memory notes in `vault/Memory/<slug>.md` with structured tags and wiki links.
   - Appends corrections and preferences to `CORRECTION_LEDGER.md` and `PREFERENCES.md`.

## Verification Commands
```bash
uv run pytest tests/test_obsidian_vault_brain.py -v
```
