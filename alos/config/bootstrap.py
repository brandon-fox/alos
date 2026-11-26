"""Composition root assembling ALOSSettings into Hexagonal Ring 2/3 components (FR-3608)."""

from __future__ import annotations

from dataclasses import dataclass, field

import alos.adapters.outbound.audit as _aud
import alos.adapters.outbound.db as _db
import alos.application.ports.outbound as _p
import alos.application.use_cases as _uc
from alos.adapters.outbound.integrations import MCPGatewayAdapter
from alos.adapters.outbound.rag import BM25VaultMemoryStore
from alos.adapters.outbound.vault import FilesystemVaultAdapter
from alos.config.settings import ALOSSettings
from alos.core.config import ALOSConfig
from alos.db.session import DatabaseManager


@dataclass
class BootstrapContainer:
    """Explicit Hexagonal dependency container wired from Factor III ALOSSettings."""

    settings: ALOSConfig
    vault: _p.VaultRepositoryPort
    memory: _p.MemoryStorePort
    audit_logger: _p.AuditLoggerPort
    decision_logger: _p.DecisionLoggerPort
    mcp_gateway: _p.MCPGatewayPort
    tracer: _aud.InMemoryTelemetryAdapter
    assemble_context: _uc.AssembleContextUseCase
    plan_action: _uc.PlanActionUseCase
    evaluate_action: _uc.EvaluateActionUseCase
    orchestrator: _uc.DualLoopOrchestrator
    _db: DatabaseManager | None = field(default=None, init=False, repr=False)

    @classmethod
    def build(
        cls,
        settings: ALOSSettings | None = None,
        approval_gate: _p.HumanApprovalGatePort | None = None,
        *,
        use_postgres_logs: bool = False,
    ) -> BootstrapContainer:
        """Instantiate canonical Ring 3 adapters, Ring 2 use cases, and orchestrator."""
        kw = settings.model_dump() if settings and not isinstance(settings, ALOSConfig) else {}
        cfg = settings if isinstance(settings, ALOSConfig) else ALOSConfig(**kw)
        tr = _aud.InMemoryTelemetryAdapter(cfg.telemetry_log_path, enabled=cfg.telemetry_enabled)
        vault, mem = FilesystemVaultAdapter(cfg.vault_dir), BM25VaultMemoryStore(cfg.vault_dir)
        mcp = MCPGatewayAdapter(mock_mode=cfg.mock_mode, tracer=tr)
        uow = _db.SqlAlchemyUnitOfWork(cfg.database_url) if use_postgres_logs else None
        alog: _p.AuditLoggerPort = (
            _db.PostgresAuditLogAdapter(uow)
            if uow
            else _aud.JsonlAuditLogAdapter(cfg.audit_log_path)
        )
        dlog: _p.DecisionLoggerPort = (
            _db.PostgresDecisionLogAdapter(uow)
            if uow
            else _aud.JsonlDecisionLogAdapter(cfg.decision_log_path)
        )
        ctx_uc = _uc.AssembleContextUseCase(vault, mem, tr)
        pln_uc, ev_uc = (
            _uc.PlanActionUseCase(tracer=tr),
            _uc.EvaluateActionUseCase(decision_logger=dlog, tracer=tr),
        )
        orch = _uc.DualLoopOrchestrator(ctx_uc, pln_uc, ev_uc, mcp, approval_gate, alog, tr)
        box = cls(cfg, vault, mem, alog, dlog, mcp, tr, ctx_uc, pln_uc, ev_uc, orch)
        box._db = uow
        return box

    def get_db(self) -> DatabaseManager:
        """Lazily initialize and return DatabaseManager bound to settings.database_url."""
        if self._db is None:
            self._db = DatabaseManager(db_url=self.settings.database_url)
        return self._db

    def close(self) -> None:
        """Dispose lazily initialized database connections and flush runtime resources."""
        if self._db is not None:
            self._db.engine.dispose()
            self._db = None

    def dispose(self) -> None:
        """Alias for close() supporting explicit resource disposal contracts."""
        self.close()

    def __enter__(self) -> BootstrapContainer:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
