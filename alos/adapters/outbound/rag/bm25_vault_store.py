"""Lazy BM25 Obsidian vault memory store adapter implementing MemoryStorePort."""

from __future__ import annotations

from alos.domain.models.context import RAGDocument
from alos.memory.vector_store import LocalVectorStore


class BM25VaultMemoryStore:
    """Lazy-indexed BM25 memory store over local Markdown vault files (MemoryStorePort)."""

    def __init__(self, vault_dir: str) -> None:
        self._store = LocalVectorStore(vault_dir)

    @property
    def is_indexed(self) -> bool:
        """Return whether the vault Markdown corpus has been lazily indexed."""
        return self._store.is_indexed

    def search(self, query: str, top_k: int = 5) -> list[RAGDocument]:
        """Search vault Markdown notes lazily and return typed RAGDocument matches."""
        return [
            RAGDocument(
                file_name=str(hit["filename"]),
                file_path=str(hit["filepath"]),
                content=str(hit["content"]),
                score=max(0.0, float(hit.get("score", 0.0))),
                source_type="vault",
            )
            for hit in self._store.search(query, top_k=top_k)
        ]
