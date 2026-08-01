"""Obsidian Graph Engine for ALOS Memory.

Spec: specs/08-obsidian-vault-brain-integration/spec.md
"""

import logging

import networkx as nx
from pydantic import BaseModel, Field

from alos.memory.obsidian_vault import ObsidianVaultParser

logger = logging.getLogger(__name__)

# Try importing compiled Rust native extension module for petgraph graph acceleration
try:
    from alos_native import FastGraphEngine  # type: ignore[import-not-found]

    HAS_RUST_NATIVE_GRAPH = True
except ImportError:
    FastGraphEngine = None
    HAS_RUST_NATIVE_GRAPH = False


class GraphNeighborhood(BaseModel):
    center_note: str
    nodes: set[str] = Field(default_factory=set)


class ObsidianGraphEngine:
    """Graph engine connecting Obsidian notes via [[WikiLink]] references.
    Uses NetworkX or petgraph native extension when available.
    """

    def __init__(self, vault_dir: str):
        self.vault_dir = vault_dir
        self.parser = ObsidianVaultParser(vault_dir=vault_dir)

    def get_neighborhood(self, center_note: str, depth: int = 2) -> GraphNeighborhood:
        notes = self.parser.parse_all()

        if HAS_RUST_NATIVE_GRAPH and FastGraphEngine:
            try:
                native_graph = FastGraphEngine()
                for note in notes:
                    name = note.file_name.rsplit(".", 1)[0]
                    native_graph.add_node(name)
                    for link in note.wiki_links:
                        native_graph.add_edge(name, link)
                visited_list = native_graph.get_neighborhood(center_note, depth)
                return GraphNeighborhood(center_note=center_note, nodes=set(visited_list))
            except Exception as err:
                logger.debug("Native FastGraphEngine unavailable or failed: %s", err)

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
