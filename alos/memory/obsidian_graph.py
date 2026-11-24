"""Obsidian Graph Engine for ALOS Memory.

Spec: specs/013-obsidian-vault-brain-integration/spec.md
"""

import importlib
import logging
from typing import Any

import networkx as nx

from alos.domain.models.memory import GraphNeighborhood
from alos.memory.obsidian_vault import ObsidianVaultParser

logger = logging.getLogger(__name__)

# Try importing compiled Rust native extension module for petgraph graph acceleration
FastGraphEngine: Any = None
try:
    FastGraphEngine = importlib.import_module("alos_native").FastGraphEngine
    HAS_RUST_NATIVE_GRAPH = True
except (ImportError, AttributeError):
    HAS_RUST_NATIVE_GRAPH = False


class ObsidianGraphEngine:
    """Graph engine connecting Obsidian notes via [[WikiLink]] references.
    Uses NetworkX or petgraph native extension when available.
    """

    def __init__(self, vault_dir: str) -> None:
        """Initialize graph engine bound to vault_dir."""
        self.vault_dir = vault_dir
        self.parser = ObsidianVaultParser(vault_dir=vault_dir)

    def get_neighborhood(
        self,
        center_note: str,
        depth: int = 2,
        *,
        use_native: bool | None = None,
        native_graph_cls: Any = None,
    ) -> GraphNeighborhood:
        """Traverse wikilink graph to find all notes within depth distance from center note."""
        notes = self.parser.parse_all()
        enabled = HAS_RUST_NATIVE_GRAPH if use_native is None else use_native
        graph_cls = FastGraphEngine if native_graph_cls is None else native_graph_cls

        if enabled and graph_cls:
            try:
                native_graph = graph_cls()
                for note in notes:
                    name = note.file_name.rsplit(".", 1)[0]
                    native_graph.add_node(name)
                    for link in note.wiki_links:
                        native_graph.add_edge(name, link)
                visited_list = native_graph.get_neighborhood(center_note, depth)
                return GraphNeighborhood(center_note=center_note, nodes=set(visited_list))
            except Exception as err:
                logger.warning("Native FastGraphEngine unavailable or failed: %s", err)

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
