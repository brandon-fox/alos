import glob
import os
from typing import Any

# Third-party library rank_bm25 lacks PEP 561 py.typed marker or type stubs
from rank_bm25 import BM25Okapi  # type: ignore[import-untyped]

from alos.core.protocols import MemoryStoreProtocol


class LocalVectorStore(MemoryStoreProtocol):
    """Local document retrieval store for Obsidian notes using Okapi BM25 (SOLID: DIP)."""

    def __init__(self, vault_dir: str):
        self.vault_dir = vault_dir

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        if not os.path.exists(self.vault_dir):
            return results

        md_files = glob.glob(os.path.join(self.vault_dir, "**", "*.md"), recursive=True)
        if not md_files:
            return results

        documents: list[dict[str, Any]] = []
        tokenized_corpus: list[list[str]] = []

        for filepath in md_files:
            filename = os.path.basename(filepath)
            try:
                with open(filepath, encoding="utf-8") as f:
                    content = f.read()
            except (OSError, UnicodeDecodeError):
                continue

            documents.append({"filename": filename, "filepath": filepath, "content": content})
            tokenized_corpus.append(content.lower().split())

        if not documents:
            return results

        tokenized_query = [t.lower() for t in query.split()]
        if not tokenized_query:
            for doc in documents[:top_k]:
                results.append({**doc, "score": 0.0})
            return results

        bm25 = BM25Okapi(tokenized_corpus)
        scores = bm25.get_scores(tokenized_query)

        scored_docs: list[dict[str, Any]] = []
        for doc, score in zip(documents, scores, strict=False):
            if score > 0:
                scored_docs.append({**doc, "score": float(score)})

        scored_docs.sort(key=lambda x: float(x["score"]), reverse=True)
        return scored_docs[:top_k]
