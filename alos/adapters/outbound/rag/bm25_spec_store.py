"""Lazy BM25 specification and vault RAG store implementing MemoryStorePort."""

from __future__ import annotations

from alos.domain.models.context import RAGDocument
from alos.domain.models.memory import SpecChunk
from alos.memory.spec_rag import SpecRAGIndexer


class BM25SpecMemoryStore:
    """Lazy-indexed spec-aware RAG adapter returning unified RAGDocument results."""

    def __init__(self, root_dir: str) -> None:
        self._indexer = SpecRAGIndexer(root_dir)

    @property
    def is_indexed(self) -> bool:
        """Return whether specification and vault chunks have been lazily indexed."""
        return self._indexer.is_indexed

    @property
    def chunks(self) -> list[SpecChunk]:
        """Return indexed specification chunks, building the index lazily on first access."""
        return self._indexer.chunks

    def search(
        self, query: str, top_k: int = 5, source_filter: str | None = None
    ) -> list[RAGDocument]:
        """Search indexed chunks lazily and return normalized RAGDocument results."""
        hits = self._indexer.search(query, top_k=top_k, source_filter=source_filter)
        return [
            RAGDocument(
                file_name=str(hit["file_name"]),
                file_path=str(hit["file_path"]),
                content=str(hit["content"]),
                score=max(0.0, float(hit.get("score", 0.0))),
                header=str(hit.get("header", "")),
                source_type=str(hit.get("source_type", "general")),
            )
            for hit in hits
        ]
