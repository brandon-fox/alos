"""Use case: assemble immutable ContextPayload from vault and semantic memory ports."""

from __future__ import annotations

from contextlib import nullcontext

from alos.application.ports.outbound import MemoryStorePort, TelemetryPort, VaultRepositoryPort
from alos.domain.models.context import ContextPayload


class AssembleContextUseCase:
    """Application query assembling context strictly through Ring 2 driven ports."""

    def __init__(
        self,
        vault: VaultRepositoryPort,
        memory_store: MemoryStorePort | None = None,
        tracer: TelemetryPort | None = None,
    ) -> None:
        self._vault, self._memory, self._tracer = vault, memory_store, tracer

    def execute(self, user_query: str, *, top_k: int = 5) -> ContextPayload:
        """Assemble immutable ContextPayload from vault knowledge and RAG hits."""
        with self._tracer.span("AssembleContextUseCase.execute") if self._tracer else nullcontext():
            rag = self._memory.search(user_query, top_k=top_k) if self._memory else []
            return ContextPayload(
                profile=self._vault.read_profile(),
                preferences=self._vault.read_list("preferences.md"),
                corrections=self._vault.read_list("corrections.md"),
                rag_docs=rag,
                wiki_links=self._vault.collect_wiki_links(),
            )
