import os
import re
from typing import Any

from pydantic import BaseModel


class SpecChunk(BaseModel):
    file_path: str
    file_name: str
    header: str
    content: str
    source_type: str


class SpecRAGIndexer:
    """Spec-aware RAG Indexer for system specs, vault notes, and reference guides."""

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
        results: list[dict[str, Any]] = []
        query_terms = [t.lower() for t in query.split()]

        for chunk in self.chunks:
            if source_filter and chunk.source_type != source_filter:
                continue

            content_lower = chunk.content.lower()
            header_lower = chunk.header.lower()

            # Score matches in header (weighted higher) and content
            score = 0
            for term in query_terms:
                if term in header_lower:
                    score += 3
                if term in content_lower:
                    score += 1

            if score > 0 or not query_terms:
                results.append(
                    {
                        "header": chunk.header,
                        "file_name": chunk.file_name,
                        "file_path": chunk.file_path,
                        "source_type": chunk.source_type,
                        "content": chunk.content,
                        "score": score,
                    }
                )

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
