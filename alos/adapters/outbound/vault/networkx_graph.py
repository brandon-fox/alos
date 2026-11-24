"""NetworkX WikiLink graph adapter with optional alos_native FastGraphEngine."""

from __future__ import annotations

from typing import Any

from alos.domain.models.memory import GraphNeighborhood
from alos.memory.obsidian_graph import ObsidianGraphEngine


class NetworkXGraphAdapter:
    """WikiLink graph traversal adapter wrapping NetworkX / petgraph graph resolution."""

    def __init__(
        self,
        vault_dir: str,
        *,
        use_native: bool | None = None,
        native_graph_cls: Any = None,
    ) -> None:
        """Initialize graph adapter bound to vault_dir and optional native graph class."""
        self.vault_dir = vault_dir
        self._engine = ObsidianGraphEngine(vault_dir)
        self._use_native = use_native
        self._native_graph_cls = native_graph_cls

    def get_neighborhood(self, center_note: str, depth: int = 2) -> GraphNeighborhood:
        """Return immutable GraphNeighborhood within cutoff hops from center_note."""
        return self._engine.get_neighborhood(
            center_note,
            depth=depth,
            use_native=self._use_native,
            native_graph_cls=self._native_graph_cls,
        )
