import os
from typing import Any

from pydantic import BaseModel, Field

from alos.core.protocols import MemoryStoreProtocol


class ContextPayload(BaseModel):
    profile: dict[str, Any] = Field(default_factory=dict)
    preferences: list[str] = Field(default_factory=list)
    corrections: list[str] = Field(default_factory=list)
    rag_docs: list[dict[str, Any]] = Field(default_factory=list)
    wiki_links: list[str] = Field(default_factory=list)


class ContextAssembler:
    """Layer 2 Context Assembler synthesizing local Markdown vault profiles,
    preferences, and corrections (SOLID: DIP).
    """

    def __init__(self, vault_dir: str, vector_store: MemoryStoreProtocol | None = None):
        from alos.memory.vector_store import LocalVectorStore

        self.vault_dir = vault_dir
        self.vector_store: MemoryStoreProtocol = (
            vector_store if vector_store is not None else LocalVectorStore(vault_dir=vault_dir)
        )

    def _collect_wiki_links(self) -> list[str]:
        from alos.memory.obsidian_vault import ObsidianVaultParser

        wiki_links: list[str] = []
        parser = ObsidianVaultParser(vault_dir=self.vault_dir)
        for note in parser.parse_all():
            for link in note.wiki_links:
                if link not in wiki_links:
                    wiki_links.append(link)
        return wiki_links

    def _read_profile(self) -> dict[str, Any]:
        profile = {}
        profile_path = os.path.join(self.vault_dir, "USER_PROFILE.md")
        if os.path.exists(profile_path):
            with open(profile_path, encoding="utf-8") as f:
                for line in f:
                    if ":" in line and not line.startswith("#"):
                        parts = line.strip().lstrip("- ").split(":", 1)
                        if len(parts) == 2:
                            profile[parts[0].strip()] = parts[1].strip()
        return profile

    def _read_vault_list(self, filename: str) -> list[str]:
        items: list[str] = []
        file_path = os.path.join(self.vault_dir, filename)
        if os.path.exists(file_path):
            with open(file_path, encoding="utf-8") as f:
                for line in f:
                    cleaned = line.strip().lstrip("- ").strip()
                    if cleaned and not line.startswith("#"):
                        items.append(cleaned)
        return items

    def assemble_context(self, user_query: str) -> ContextPayload:
        wiki_links = self._collect_wiki_links()
        profile = self._read_profile()
        preferences = self._read_vault_list("PREFERENCES.md")
        corrections = self._read_vault_list("CORRECTION_LEDGER.md")
        rag_results = self.vector_store.search(user_query, top_k=3)

        return ContextPayload(
            profile=profile,
            preferences=preferences,
            corrections=corrections,
            rag_docs=rag_results,
            wiki_links=wiki_links,
        )
