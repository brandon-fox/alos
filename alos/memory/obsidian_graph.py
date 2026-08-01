"""Obsidian Graph Engine for ALOS Memory.

Spec: specs/08-obsidian-vault-brain-integration/spec.md
"""

from collections import deque

from pydantic import BaseModel, Field

from alos.memory.obsidian_vault import ObsidianVaultParser


class GraphNeighborhood(BaseModel):
    center_note: str
    nodes: set[str] = Field(default_factory=set)


class ObsidianGraphEngine:
    """Graph engine connecting Obsidian notes via [[WikiLink]] references."""

    def __init__(self, vault_dir: str):
        self.vault_dir = vault_dir
        self.parser = ObsidianVaultParser(vault_dir=vault_dir)

    def get_neighborhood(self, center_note: str, depth: int = 2) -> GraphNeighborhood:
        notes = self.parser.parse_all()

        # Build adjacency mapping (bidirectional for note graph)
        adj: dict[str, set[str]] = {}
        for note in notes:
            name = note.file_name.rsplit(".", 1)[0]
            if name not in adj:
                adj[name] = set()
            for link in note.wiki_links:
                adj[name].add(link)
                if link not in adj:
                    adj[link] = set()
                adj[link].add(name)

        visited: set[str] = {center_note}
        queue: deque[tuple[str, int]] = deque([(center_note, 0)])

        while queue:
            curr, curr_depth = queue.popleft()
            if curr_depth < depth:
                neighbors = adj.get(curr, set())
                for nxt in neighbors:
                    if nxt not in visited:
                        visited.add(nxt)
                        queue.append((nxt, curr_depth + 1))

        return GraphNeighborhood(center_note=center_note, nodes=visited)
