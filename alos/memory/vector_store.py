"""Local document vector store using lazy-indexed BM25 scoring."""

from __future__ import annotations

import glob
import logging
import os
from typing import Any

# Third-party library rank_bm25 lacks PEP 561 py.typed marker or type stubs
from rank_bm25 import BM25Okapi  # type: ignore[import-untyped]

from alos.core.protocols import MemoryStoreProtocol

logger = logging.getLogger(__name__)


class LocalVectorStore(MemoryStoreProtocol):
    """Local document retrieval store for Obsidian notes using lazy Okapi BM25 (SOLID: DIP)."""

    def __init__(self, vault_dir: str) -> None:
        self.vault_dir = vault_dir
        self._indexed = False
        self._docs: list[dict[str, str]] = []
        self._bm25: Any = None

    @property
    def is_indexed(self) -> bool:
        """Return whether the vault corpus has been lazily indexed."""
        return self._indexed

    def _ensure_index(self) -> None:
        if self._indexed:
            return
        self._indexed = True
        if not os.path.exists(self.vault_dir):
            return
        corpus: list[list[str]] = []
        for filepath in glob.glob(os.path.join(self.vault_dir, "**", "*.md"), recursive=True):
            try:
                with open(filepath, encoding="utf-8") as handle:
                    content = handle.read()
            except (OSError, UnicodeDecodeError) as err:
                logger.warning("Skipping unreadable vault note %s: %s", filepath, err)
                continue
            self._docs.append(
                {"filename": os.path.basename(filepath), "filepath": filepath, "content": content}
            )
            corpus.append(content.lower().split())
        if corpus:
            self._bm25 = BM25Okapi(corpus)

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Search local vault markdown files lazily using BM25 relevance scoring."""
        self._ensure_index()
        if not self._docs or top_k <= 0 or self._bm25 is None:
            return []
        tokenized_query = [tok.lower() for tok in query.split()]
        if not tokenized_query:
            return [{**doc, "score": 0.0} for doc in self._docs[:top_k]]
        scores = self._bm25.get_scores(tokenized_query)
        ranked = sorted(
            ((float(s), doc) for doc, s in zip(self._docs, scores, strict=False) if s > 0),
            key=lambda pair: pair[0],
            reverse=True,
        )
        return [{**doc, "score": score} for score, doc in ranked[:top_k]]
