import os
from typing import Any

from pydantic import BaseModel, Field

from alos.memory.vector_store import LocalVectorStore


class ContextPayload(BaseModel):
    profile: dict[str, Any] = Field(default_factory=dict)
    preferences: list[str] = Field(default_factory=list)
    corrections: list[str] = Field(default_factory=list)
    rag_docs: list[dict[str, Any]] = Field(default_factory=list)


class ContextAssembler:
    """Layer 2 Context Assembler synthesizing local Markdown vault profiles,
    preferences, and corrections.
    """

    def __init__(self, vault_dir: str):
        self.vault_dir = vault_dir
        self.vector_store = LocalVectorStore(vault_dir=vault_dir)

    def assemble_context(self, user_query: str) -> ContextPayload:
        profile = {}
        preferences = []
        corrections = []

        # Read USER_PROFILE.md
        profile_path = os.path.join(self.vault_dir, "USER_PROFILE.md")
        if os.path.exists(profile_path):
            with open(profile_path, encoding="utf-8") as f:
                for line in f:
                    if ":" in line and not line.startswith("#"):
                        parts = line.strip().lstrip("- ").split(":", 1)
                        if len(parts) == 2:
                            profile[parts[0].strip()] = parts[1].strip()

        # Read PREFERENCES.md
        pref_path = os.path.join(self.vault_dir, "PREFERENCES.md")
        if os.path.exists(pref_path):
            with open(pref_path, encoding="utf-8") as f:
                for line in f:
                    cleaned = line.strip().lstrip("- ").strip()
                    if cleaned and not line.startswith("#"):
                        preferences.append(cleaned)

        # Read CORRECTION_LEDGER.md
        corr_path = os.path.join(self.vault_dir, "CORRECTION_LEDGER.md")
        if os.path.exists(corr_path):
            with open(corr_path, encoding="utf-8") as f:
                for line in f:
                    cleaned = line.strip().lstrip("- ").strip()
                    if cleaned and not line.startswith("#"):
                        corrections.append(cleaned)

        # Vector RAG search over notes
        rag_results = self.vector_store.search(user_query, top_k=3)

        return ContextPayload(
            profile=profile,
            preferences=preferences,
            corrections=corrections,
            rag_docs=rag_results,
        )
