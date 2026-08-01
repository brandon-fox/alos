import glob
import os
from typing import Any


class LocalVectorStore:
    """Local vector / document retrieval store for Obsidian Markdown Vault notes."""

    def __init__(self, vault_dir: str):
        self.vault_dir = vault_dir

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        if not os.path.exists(self.vault_dir):
            return results

        md_files = glob.glob(os.path.join(self.vault_dir, "**", "*.md"), recursive=True)
        query_terms = [t.lower() for t in query.split()]

        for filepath in md_files:
            filename = os.path.basename(filepath)
            try:
                with open(filepath, encoding="utf-8") as f:
                    content = f.read()
            except (OSError, UnicodeDecodeError):
                continue

            content_lower = content.lower()
            score = sum(1 for term in query_terms if term in content_lower)

            if score > 0 or not query_terms:
                results.append(
                    {"filename": filename, "filepath": filepath, "content": content, "score": score}
                )

        results.sort(key=lambda x: int(x["score"]), reverse=True)
        return results[:top_k]
