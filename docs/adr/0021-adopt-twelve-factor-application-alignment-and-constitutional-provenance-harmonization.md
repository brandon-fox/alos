# Adopt Twelve-Factor Application Alignment and Constitutional Provenance Harmonization

* Status: accepted
* Deciders: Brandon Fox
* Date: 2026-11-24

Technical Story: `specs/036-hexagonal-twelve-factor-refactor/spec.md`

## Context and Problem Statement

ALOS exhibits drift across Twelve-Factor principles II through XII: undeclared direct runtime dependencies (`pyyaml`, `pydantic-settings`) and unpinned `pip install` in `Dockerfile*` bypassing `uv.lock` (II, V); scattered `os.getenv`, hardcoded DB credentials, and import-time `os.environ` mutations in `alos/crews/config.py` and `alos/db/session.py` (III); inline `mock_mode` stubs in `N8nClient` and `MCPGateway` plus raw `open()` vault reads in `ContextAssembler` (IV, X); mutable process singletons (`global_tracer`, `SpecKitPluginRegistry._instance`) and resetting `D-001` counters in `DecisionLogger` (VI); missing inbound server port-binding and `SIGTERM`/`SIGINT` drain (`scheduler.shutdown(wait=False)`) (VII, VIII, IX); raw `print()` and silent `except` blocks instead of `stdout`/`stderr` streams (XI); and fragmented admin scripts bypassing `ALOSConfig` and Alembic (XII). How do we achieve 100% 12-Factor compliance while honoring Constitution Articles III and VI (`logs/decision_log.jsonl`, `logs/system_audit.jsonl`, and local Markdown `vault/` restoration)?

## Decision Drivers

* Enforce strict dependency isolation (`uv sync --frozen`) and build/release/run separation across wheel, PyO3 native extension, and container artifacts.
* Eliminate all import-time `os.environ` reads/mutations, process-global mutable singletons, and session-resetting `D-NNN` journal ID collisions.
* Harmonize Factor XI (`stdout`/`stderr` event-stream diagnostics) with Constitution Articles III and VI (immutable local JSONL provenance ledgers and Markdown vault state).
* Guarantee fast startup and deterministic `SIGTERM`/`SIGINT` graceful shutdown across schedulers, DB pools, child `ollama` servers, and sandbox containers.
* Consolidate one-off admin tasks (`db`, `speckit`, `swarm`) under a unified `[project.scripts]` `alos` CLI sharing identical release code and settings.

## Considered Options

* Option 1: Full Twelve-Factor alignment with Constitutional Provenance Harmonization (Factor XI `stdout`/`stderr` operational streams + Factor IV attached JSONL/Vault/PostgreSQL provenance backing services)
* Option 2: Cloud-only Twelve-Factor replacement discarding local JSONL journals and Markdown `vault/` in favor of mandatory PostgreSQL, Redis, and external log aggregators
* Option 3: Container-surface patching (`Dockerfile` and `.env` updates only) while retaining module-level `os.getenv`, process singletons, and inline `mock_mode` branches

## Decision Outcome

Chosen option: "Option 1: Full Twelve-Factor alignment with Constitutional Provenance Harmonization (Factor XI `stdout`/`stderr` operational streams + Factor IV attached JSONL/Vault/PostgreSQL provenance backing services)", because it achieves complete 12-Factor compliance for processes, config, build/release/run, disposability, and operational event streams while preserving ALOS Constitutional local-first data sovereignty and append-only provenance ledgers as swappable Factor IV backing services.

### Positive Consequences

* Separates operational diagnostics (structured JSON/text to `stdout`/`stderr`) from domain audit/decision provenance (`AuditLoggerPort` and `DecisionLoggerPort` backed by JSONL or PostgreSQL).
* Eliminates duplicate `D-001` journal collisions across restarts and guarantees clean `SIGTERM`/`SIGINT` resource teardown (`wait=True` drain, DB pool `dispose()`, child process cleanup).
* Produces reproducible container and wheel releases via `uv sync --frozen` and `[project.scripts]` (`alos = "alos.cli:main"`).

### Negative Consequences

* Requires refactoring constructor-time `os.makedirs` side effects and singleton registries into an explicit startup/bootstrap lifecycle.
* Requires maintaining adapter parity between local filesystem/SQLite backing services and PostgreSQL/HTTP backing services.

## Pros and Cons of the Options

### Option 1: Full Twelve-Factor alignment with Constitutional Provenance Harmonization

* Good, because every factor (I-XII) is satisfied without violating Constitution Articles II, III, or VI.
* Good, because swapping between local JSONL/Markdown backing stores and PostgreSQL/MCP endpoints becomes purely a configuration change (`ALOSSettings`).
* Bad, because dual-nature logging (diagnostic `stdout` vs provenance ledger port) must be clearly separated in adapter contracts.

### Option 2: Cloud-only Twelve-Factor replacement discarding local JSONL journals and Markdown `vault/`

* Good, because all persistence lives in networked PostgreSQL and external log collectors.
* Bad, because it directly violates Constitution Article VI (stateless restart from local Markdown vault and transaction logs without mandatory persistent DB daemons).

### Option 3: Container-surface patching (`Dockerfile` and `.env` updates only)

* Good, because initial diff size is small.
* Bad, because import-time env binding, `global_tracer` race conditions, inline `mock_mode` code paths, and ungraceful `SIGTERM` exits remain broken in production.

## Links

* Refines [ADR-0006](0006-capture-runtime-action-decisions-with-decisionlogger-adr-records.md)
* Refines [ADR-0007](0007-adopt-sqlalchemy-orm-and-alembic-for-postgresql-data-models-and-migrations.md)
* Refines [ADR-0011](0011-adopt-dual-repo-open-source-architecture-and-public-ci-cd-pipeline.md)
