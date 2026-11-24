"""Hexagonal Ring 2 outbound (driven) port protocols for infrastructure adapters."""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any, Protocol, runtime_checkable

import alos.domain.models.audit as aud
import alos.domain.models.context as ctx
import alos.domain.models.speckit as spk
import alos.domain.models.workflow as wf
from alos.domain.models.actions import BaseAction as _Act
from alos.domain.models.evaluation import EvaluationResult as _Eval

_Map = dict[str, Any]
_Lbl = dict[str, str] | None
_Bk = tuple[float, ...] | None
_CM = AbstractContextManager[Any]


@runtime_checkable
class TelemetryPort(Protocol):
    """Driven port for tracing spans and runtime telemetry metrics (ISP & DIP)."""

    def span(self, name: str, tags: _Map | None = None, traceparent: str | None = None) -> _CM:
        """Return a context manager wrapping a trace span."""

    def inc_counter(self, name: str, amount: float = 1.0, labels: _Lbl = None) -> float:
        """Increment a named counter metric."""

    def set_gauge(self, name: str, value: float, labels: _Lbl = None) -> float:
        """Set a named gauge metric."""

    def observe_histogram(
        self, n: str, val: float, labels: _Lbl = None, buckets: _Bk = None
    ) -> Any:
        """Observe a value on a named histogram metric."""


@runtime_checkable
class VaultRepositoryPort(Protocol):
    """Driven port for Obsidian vault profile, rules, links, and note persistence."""

    def read_profile(self) -> _Map:
        """Read structured user profile metadata from the vault."""

    def read_list(self, filename: str) -> list[str]:
        """Read normalized non-empty bulleted entries from a vault markdown file."""

    def collect_wiki_links(self) -> list[str]:
        """Collect vault note backlinks and wiki-links."""


@runtime_checkable
class MemoryStorePort(Protocol):
    """Driven port returning typed RAGDocument chunks for semantic memory search."""

    def search(self, query: str, top_k: int = 5) -> list[ctx.RAGDocument]:
        """Return the top-k matching RAGDocument results."""


@runtime_checkable
class AuditLoggerPort(Protocol):
    """Driven port for immutable AuditEvent persistence."""

    def log_audit_event(self, event: aud.AuditEvent) -> _Map:
        """Persist an immutable AuditEvent and return serialized record data."""


@runtime_checkable
class DecisionLoggerPort(Protocol):
    """Driven port for immutable Constitution DecisionRecord persistence."""

    def log_decision_record(self, record: aud.DecisionRecord) -> _Map:
        """Persist an immutable DecisionRecord and return serialized record data."""


@runtime_checkable
class MCPGatewayPort(Protocol):
    """Driven port dispatching named external tool calls."""

    def execute_tool(self, tool_name: str, payload: _Map) -> _Map:
        """Execute a named tool with payload and return structured response."""


@runtime_checkable
class HumanApprovalGatePort(Protocol):
    """Driven port gating HIGH-risk actions on explicit human confirmation (FR-3609)."""

    def request_approval(self, action: _Act, evaluation: _Eval, *, trigger: str = "") -> bool:
        """Return True if a human operator approves executing the HIGH-risk action."""


@runtime_checkable
class WorkflowOrchestratorPort(Protocol):
    """Driven port for n8n or external workflow webhook orchestration."""

    def trigger_workflow(self, payload: _Map) -> wf.N8nExecutionResponse:
        """Trigger workflow orchestration and return typed N8nExecutionResponse."""


@runtime_checkable
class SpecKitRepositoryPort(Protocol):
    """Driven port for persisting SpecKit LifecycleRecord artifacts."""

    def load_record(self, feature_name: str) -> spk.LifecycleRecord:
        """Load the LifecycleRecord for a feature."""

    def save_record(self, record: spk.LifecycleRecord) -> None:
        """Persist an updated LifecycleRecord."""
