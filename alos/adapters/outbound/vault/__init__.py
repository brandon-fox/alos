"""Outbound Obsidian vault and WikiLink graph infrastructure adapters (ADR-0024)."""

from alos.adapters.outbound.vault.filesystem_vault import FilesystemVaultAdapter
from alos.adapters.outbound.vault.networkx_graph import NetworkXGraphAdapter

__all__ = ["FilesystemVaultAdapter", "NetworkXGraphAdapter"]
