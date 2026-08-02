import logging
import os
import re
from typing import Any

from pydantic import BaseModel

# Third-party library rank_bm25 lacks PEP 561 py.typed marker or type stubs
from rank_bm25 import BM25Okapi  # type: ignore[import-untyped]

from alos.core.protocols import MemoryStoreProtocol
from alos.native import get_bm25_indexer

logger = logging.getLogger(__name__)


class SpecChunk(BaseModel):
    file_path: str
    file_name: str
    header: str
    content: str
    source_type: str


class SpecRAGIndexer(MemoryStoreProtocol):
    """Spec-aware RAG Indexer for specs and vault notes using BM25 (SOLID: DIP)."""

    def __init__(self, root_dir: str):
        self.root_dir = os.path.abspath(root_dir)
        self.chunks: list[SpecChunk] = []
        self._build_index()

    def _determine_source_type(self, rel_path: str) -> str:
        rel_path_lower = rel_path.lower()
        if "constitution" in rel_path_lower:
            return "constitution"
        elif "vault" in rel_path_lower:
            return "vault"
        elif "specs" in rel_path_lower:
            return "spec"
        elif "references" in rel_path_lower:
            return "reference"
        return "general"

    def _chunk_markdown(self, file_path: str, content: str, source_type: str) -> list[SpecChunk]:
        file_name = os.path.basename(file_path)
        chunks: list[SpecChunk] = []

        # Split markdown by top-level or second-level headers (# or ## or ###)
        sections = re.split(r"(^|\n)(?=#+\s+)", content)
        for sec in sections:
            sec_trimmed = sec.strip()
            if not sec_trimmed:
                continue

            lines = sec_trimmed.splitlines()
            header = "General"
            if lines[0].startswith("#"):
                header = lines[0].lstrip("#").strip()

            chunks.append(
                SpecChunk(
                    file_path=file_path,
                    file_name=file_name,
                    header=header,
                    content=sec_trimmed,
                    source_type=source_type,
                )
            )

        return chunks

    def _build_index(self) -> None:
        self.chunks.clear()

        # Scan specs/, vault/, references/, .specify/memory/
        search_dirs = [
            os.path.join(self.root_dir, "specs"),
            os.path.join(self.root_dir, "vault"),
            os.path.join(self.root_dir, "references"),
            os.path.join(self.root_dir, ".specify", "memory"),
        ]

        for s_dir in search_dirs:
            if not os.path.exists(s_dir):
                continue

            for root, _, files in os.walk(s_dir):
                for file in files:
                    if file.endswith((".md", ".feature")):
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, self.root_dir)
                        source_type = self._determine_source_type(rel_path)

                        try:
                            with open(full_path, encoding="utf-8") as f:
                                content = f.read()
                            file_chunks = self._chunk_markdown(full_path, content, source_type)
                            self.chunks.extend(file_chunks)
                        except (OSError, UnicodeDecodeError):
                            continue

    def search(
        self, query: str, top_k: int = 5, source_filter: str | None = None
    ) -> list[dict[str, Any]]:
        filtered_chunks = [
            c for c in self.chunks if not source_filter or c.source_type == source_filter
        ]
        if not filtered_chunks:
            return []

        try:
            indexer = get_bm25_indexer()
            for c in self.chunks:
                indexer.add_chunk(c.header, c.file_name, c.file_path, c.source_type, c.content)
            native_res: list[dict[str, Any]] = list(indexer.search(query, top_k, source_filter))
            if native_res:
                return native_res
        except Exception as err:
            logger.debug("Native FastBM25Indexer search failed: %s", err)

        tokenized_query = [t.lower() for t in query.split()]
        if not tokenized_query:
            results: list[dict[str, Any]] = []
            for chunk in filtered_chunks[:top_k]:
                results.append(
                    {
                        "header": chunk.header,
                        "file_name": chunk.file_name,
                        "file_path": chunk.file_path,
                        "source_type": chunk.source_type,
                        "content": chunk.content,
                        "score": 0.0,
                    }
                )
            return results

        # Header terms boosted in tokenized chunk corpus
        tokenized_corpus = [
            f"{c.header} {c.header} {c.header} {c.content}".lower().split() for c in filtered_chunks
        ]
        bm25 = BM25Okapi(tokenized_corpus)
        scores = bm25.get_scores(tokenized_query)

        scored_results: list[dict[str, Any]] = []
        for chunk, score in zip(filtered_chunks, scores, strict=False):
            if score > 0:
                scored_results.append(
                    {
                        "header": chunk.header,
                        "file_name": chunk.file_name,
                        "file_path": chunk.file_path,
                        "source_type": chunk.source_type,
                        "content": chunk.content,
                        "score": float(score),
                    }
                )

        scored_results.sort(key=lambda x: float(x["score"]), reverse=True)
        return scored_results[:top_k]
