"""Obsidian Graph Engine for ALOS Memory.

Spec: specs/08-obsidian-vault-brain-integration/spec.md
"""

import networkx as nx
from pydantic import BaseModel, Field

from alos.memory.obsidian_vault import ObsidianVaultParser


class GraphNeighborhood(BaseModel):
    center_note: str
    nodes: set[str] = Field(default_factory=set)


class ObsidianGraphEngine:
    """Graph engine connecting Obsidian notes via [[WikiLink]] references using NetworkX."""

    def __init__(self, vault_dir: str):
        self.vault_dir = vault_dir
        self.parser = ObsidianVaultParser(vault_dir=vault_dir)

    def get_neighborhood(self, center_note: str, depth: int = 2) -> GraphNeighborhood:
        notes = self.parser.parse_all()

        # Build NetworkX undirected graph
        graph: nx.Graph = nx.Graph()
        for note in notes:
            name = note.file_name.rsplit(".", 1)[0]
            graph.add_node(name)
            for link in note.wiki_links:
                graph.add_edge(name, link)

        if not graph.has_node(center_note):
            return GraphNeighborhood(center_note=center_note, nodes={center_note})

        # Retrieve nodes within specified cutoff depth using NetworkX
        lengths = nx.single_source_shortest_path_length(graph, center_note, cutoff=depth)
        visited = set(lengths.keys())

        return GraphNeighborhood(center_note=center_note, nodes=visited)
