# Feature Specification: Twelve-Factor, Pydantic v2, SOLID & Hexagonal Architecture Refactor

**Feature Branch**: `hexagonal_architecture_refactor` (`036-hexagonal-twelve-factor-refactor`)

**Created**: 2026-11-24

**Status**: Approved for Incremental PR Execution

**Architecture Decisions**: [ADR-0021](../../docs/adr/0021-adopt-twelve-factor-application-alignment-and-constitutional-provenance-harmonization.md), [ADR-0022](../../docs/adr/0022-standardize-configuration-on-pydantic-settings-and-domain-data-on-frozen-pydantic-v2-models.md), [ADR-0023](../../docs/adr/0023-enforce-solid-principles-via-composable-policy-registries-and-segregated-cqrs-ports.md), [ADR-0024](../../docs/adr/0024-adopt-hexagonal-ports-and-adapters-architecture-via-strangler-fig-incremental-prs.md)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Unified Environment Configuration & Validated Domain Schemas (Priority: P1)

As an ALOS operator and developer, I want all runtime configuration loaded dynamically from environment variables and `.env` files into validated settings objects, and all domain actions, context records, audit events, and RAG results enforced as immutable, strictly validated schemas, so misconfigurations and malformed payloads fail deterministically at system boundaries before any side effect occurs.

**Why this priority**: Foundation for Twelve-Factor Factor III and Constitution Article I; every higher-level service and adapter depends on canonical configuration and immutable domain contracts.

**Independent Test**: Override environment variables in isolation (`monkeypatch.setenv` and temporary `.env`), instantiate runtime configuration without import-time side effects, and attempt to construct action/audit/RAG models with invalid or unknown fields.

**Acceptance Scenarios**:

1. **Given** environment overrides or a local `.env` file, **When** configuration is instantiated at runtime, **Then** all database, vault, workflow, log, LLM, and secret settings resolve without mutating `os.environ` at module import time.
2. **Given** an action draft, evaluation result, decision record, or RAG search document containing unknown fields or invalid field types, **When** boundary validation runs, **Then** construction fails deterministically and immutable instances reject post-creation mutation.

---

### User Story 2 - Composable Safety Policies, Segregated Ports & Human Approval Gate (Priority: P1)

As the ALOS user governed by the Safety Matrix, I want risk classification, vault preferences, and correction ledger checks executed by composable domain policies behind segregated read/write ports--with `HIGH`-risk actions gated on explicit human approval prior to external tool dispatch--so adding rules never requires modifying core orchestrators and high-risk mutations never bypass human consent.

**Why this priority**: Closes an active Constitution Article V safety gap (`HIGH`-risk actions previously dispatched immediately when rule-valid) and establishes SOLID SRP, OCP, LSP, ISP, and DIP boundaries.

**Independent Test**: Register a custom preference policy without modifying the evaluator class, run both mocked (`@mocked`) and live (`@live`) dual-loop evaluations for `LOW`, `MEDIUM`, and `HIGH` risk actions, and verify `HIGH`-risk actions halt at the approval port while emitting a complete Decision Log entry.

**Acceptance Scenarios**:

1. **Given** a `HIGH`-risk action (`EmailDraft` or `EmailSend`) that passes preference validation, **When** the dual-loop orchestrator evaluates the draft, **Then** external tool execution is blocked until the approval gate port returns explicit approval, and a `DecisionRecord` is persisted first.
2. **Given** a newly registered preference or correction rule, **When** an action violates that rule, **Then** evaluation rejects the draft and triggers self-correction without modifying core evaluator orchestration code.
3. **Given** CrewAI safety evaluation or pure-Python fallback BM25 search, **When** invoked alongside native Rust acceleration, **Then** risk tiers, zero-match filtering, and Decision Log emission behave identically across implementations.

---

### User Story 3 - Hexagonal Ports & Adapters Isolation Without Circular Imports (Priority: P2)

As an ALOS maintainer, I want pure domain models and policies isolated from application use cases and inbound/outbound infrastructure adapters, so domain and application logic execute with zero filesystem, database, or network dependencies and zero circular package imports.

**Why this priority**: Eliminates the three existing bidirectional package cycles (`core <-> logs`, `core <-> memory`, `core <-> integrations`) while preserving backwards-compatible re-export shims across incremental pull requests.

**Independent Test**: Run the AST architectural boundary suite to confirm zero outward imports from `domain` or `application`, and run the existing test suite unmodified through legacy re-export shims.

**Acceptance Scenarios**:

1. **Given** the refactored package hierarchy, **When** AST dependency analysis inspects `alos/domain` and `alos/application`, **Then** zero imports target `alos/adapters`, `alos/config`, SQLAlchemy, filesystem I/O, or external SDK clients.
2. **Given** existing callers and BDD suites importing legacy module paths, **When** intermediate pull requests merge to `main`, **Then** 100% of existing imports and behavioral contracts pass without regression.

---

### User Story 4 - Twelve-Factor Process Disposability, Event-Stream Diagnostics & Admin Parity (Priority: P2)

As a platform operator running ALOS locally or in containers, I want stateless worker processes, structured `stdout`/`stderr` operational diagnostics separated from provenance ledgers, deterministic `SIGTERM`/`SIGINT` graceful shutdown, locked hermetic container builds, and unified CLI admin subcommands.

**Why this priority**: Completes Twelve-Factor alignment across Factors II, IV, V, VI, VII, VIII, IX, X, XI, and XII.

**Independent Test**: Launch CLI, scheduler, and container entrypoints under mocked and live Backing Services, send `SIGTERM`/`SIGINT`, and verify in-flight work drains cleanly, diagnostic events stream to `stdout`/`stderr`, and provenance IDs (`D-NNN`) increment monotonically across restarts.

**Acceptance Scenarios**:

1. **Given** an existing `decision_log.jsonl` containing prior `D-001..D-005` records, **When** a fresh process starts and logs a decision, **Then** the next record is assigned `D-006` without collision.
2. **Given** a running scheduler or worker receiving `SIGTERM` or `SIGINT`, **When** shutdown initiates, **Then** active tasks drain (`wait=True`), database pools dispose, child servers/containers terminate cleanly, and diagnostic logs emit to `stdout`/`stderr`.

### Edge Cases

- Missing `.env` file or unset optional environment variables fall back to safe local-first defaults (`vault`, `logs/*.jsonl`) without hardcoded production credentials.
- `SpanContext` inside active telemetry `with tracer.span(...) as span:` permits status updates while rejecting unknown attributes, and concurrent threads recording spans/metrics do not race.
- `alos/swarm/dispatcher.py` and `alos/swarm/sandbox.py` remain strictly standard-library-only per Specs 029 and 030 while adapting cleanly to Hexagonal outbound ports and `SIGTERM` traps.
- Concurrent PRs or unmerged worktrees modifying `pyproject.toml`, `alos/cli.py`, `docs/adr/`, or `specs/` rebase deterministically within the `<= 1000`-line PR size cap.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-3601**: System MUST declare all direct runtime dependencies (`pydantic-settings`, `pyyaml`) in `pyproject.toml`, expose `[project.scripts]` (`alos = "alos.cli:main"`), and build containers hermetically from `uv.lock` (Twelve-Factor II, V).
- **FR-3602**: System MUST centralize all environment configuration into `ALOSSettings` (`BaseSettings`) with `.env` support, `SecretStr` secrets, and zero import-time `os.environ` reads or mutations (Twelve-Factor III; ADR-0022).
- **FR-3603**: System MUST enforce `ConfigDict(frozen=True, extra="forbid")` on all domain entities, action schemas (with `Literal` discriminated `action_type` and `EmailSend`), `EvaluationResult`, `ContextPayload`, `DecisionRecord`, `AuditEvent`, and `RAGDocument` (ADR-0022).
- **FR-3604**: System MUST preserve `ConfigDict(extra="forbid", validate_assignment=True)` on `SpanContext` and guard `TelemetryTracer` collections with a `threading.Lock` without unbounded global state leaks (Twelve-Factor VI; ADR-0021, ADR-0022).
- **FR-3605**: System MUST decompose `ALOSStateGraph`, `EvaluatorNode`, `ContextAssembler`, `N8nClient`, and `SpecRAGIndexer` into single-responsibility domain policies, application use cases, and infrastructure adapters with per-function Cyclomatic Complexity `<= 12` (SOLID SRP; ADR-0023).
- **FR-3606**: System MUST replace closed `if/elif` rule, planner, workflow, and tool dispatch branches with extensible `PolicyRuleRegistry`, `ActionDraftStrategyRegistry`, and `ToolHandlerRegistry` abstractions (SOLID OCP; ADR-0023).
- **FR-3607**: System MUST unify `MemoryStoreProtocol` implementations on typed `RAGDocument` results and fix `FallbackBM25Indexer` so non-matching queries return empty/zero-score hits consistent with `alos_native` and `BM25Okapi` (SOLID LSP; Twelve-Factor X).
- **FR-3608**: System MUST segregate outbound `typing.Protocol` ports by read/write responsibility (`VaultReaderPort`, `VaultWriterPort`, `DecisionLoggerPort` accepting `DecisionRecord`, `AuditLoggerPort` accepting `AuditEvent`, `HumanApprovalGatePort`, `PlannerPort`, `WorkflowAutomationPort`, `DbUnitOfWorkPort`) (SOLID ISP, DIP; ADR-0023).
- **FR-3609**: System MUST gate all `RiskLevel.HIGH` actions behind `HumanApprovalGatePort` in `DualLoopOrchestrator` before invoking `MCPGatewayProtocol`, and route CrewAI `SafetyEvaluatorTool` through `EvaluateActionUseCase` so every evaluation persists a `DecisionRecord` (Constitution III, V; SOLID DIP).
- **FR-3610**: System MUST organize source packages into four inward-pointing Hexagonal rings (`alos/domain`, `alos/application`, `alos/adapters/{inbound,outbound}`, `alos/config`) verified by an automated AST import-boundary meta-test and free of `PLC0415` package cycles (ADR-0024).
- **FR-3611**: System MUST maintain backwards-compatible re-export shims at legacy `alos.{core,schemas,logs,memory,integrations,db,engine,crews}` module paths across all intermediate migration pull requests (ADR-0024).
- **FR-3612**: System MUST separate operational event-stream logging (`stdout`/`stderr` structured formatter, zero raw `print()` or silent `except: pass`) from Factor IV provenance backing adapters (`JsonlDecisionLogAdapter`, `JsonlAuditLogAdapter`, `PostgresDecisionLogAdapter`, `PostgresAuditLogAdapter`) (Twelve-Factor IV, XI; ADR-0021).
- **FR-3613**: System MUST recover the next monotonic `D-NNN` sequence from existing provenance records rather than resetting an in-memory counter to `D-001` on startup (Twelve-Factor VI; ADR-0021).
- **FR-3614**: System MUST register `SIGTERM`/`SIGINT` handlers in long-running entrypoints (`scheduler`, `inbound server`, `swarm dispatcher/sandbox`) to drain active jobs (`shutdown(wait=True)`), dispose SQLAlchemy pools, and clean up child processes/containers (Twelve-Factor VII, VIII, IX).
- **FR-3615**: System MUST expose unified one-off admin subcommands (`alos db upgrade`, `alos speckit ...`, `alos health`) sharing the Composition Root (`alos/config/bootstrap.py`) while keeping `alos/swarm/{dispatcher,sandbox}.py` stdlib-only (Twelve-Factor XII; Specs 029, 030).
- **FR-3616**: Every refactor increment MUST deliver an independently testable `200-400` line slice (clearing the `400`-line soft warning and `1,000`-line hard gate), include `@mocked` and `@live` BDD scenarios, sustain `>= 90%` coverage (`>= 75%` MyPy file precision), and pass all required CI status checks (ADR-0024).
- **FR-3617**: Every created or refactored module, public class, and public function MUST carry accurate Google/PEP-257 docstrings (`audit-docstrings` == 0 missing), updated inline architectural/ring-boundary design comments, and zero `TODO|FIXME|HACK|XXX|NOSONAR` debt markers.
- **FR-3618**: Documentation and architectural diagrams across `docs/architecture.md`, `README.md` (preserving First-ADE Axioms `A1`, `A8`, `A9`), `docs/getting_started.md`, `docs/specs_setup.md`, and regenerated `docs/traceability.md` MUST match the live Hexagonal topology, Twelve-Factor CLI, and SQLAlchemy models with zero stale references.

### Key Entities

- **`ALOSSettings`**: Hierarchical environment-backed configuration root (`VaultSettings`, `JournalSettings`, `DatabaseSettings`, `LLMSettings`, `WorkflowSettings`, `ObservabilitySettings`).
- **`BaseAction` / Action Union**: Immutable discriminated union (`TodoistTaskCreate`, `GoogleCalendarEvent`, `EmailDraft`, `EmailSend`, `VaultNoteUpdate`, `WebSearchQuery`).
- **`DecisionRecord` & `AuditEvent`**: Immutable provenance domain events persisted to attached JSONL and/or PostgreSQL backing adapters prior to external mutations.
- **`ContextPayload` & `RAGDocument`**: Immutable assembled user profile, preferences, corrections, graph links, and normalized retrieval hits.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of modules under `alos/domain` and `alos/application` have zero outward imports to infrastructure adapters or SDKs, verified automatically on every test run.
- **SC-002**: 100% of environment variables in `.env.example` and runtime entrypoints resolve through `ALOSSettings` with zero direct `os.getenv` calls outside `alos/config/settings.py` and stdlib-isolated `alos/swarm/` workers.
- **SC-003**: 100% of `HIGH`-risk actions block external execution until explicit approval is granted, and 100% of evaluator invocations (including CrewAI tools) emit a monotonically numbered `DecisionRecord`.
- **SC-004**: Every incremental pull request in the 16-PR migration stack targets `200-400` non-lockfile lines (`<= 400` soft warning, `< 1,000` hard gate), passes all required CI checks and post-merge audit scanners (zero missing public docstrings, zero debt markers, `CC <= 10`, MyPy file precision `>= 75%`, branch test coverage `>= 90%`), and synchronizes all architectural diagrams and user docs.

## Assumptions

- Local Markdown `vault/` and append-only JSONL ledgers remain default local-first Factor IV backing services per Constitution Articles II, III, and VI, with PostgreSQL and HTTP/MCP adapters selectable via `ALOSSettings`.
- `alos/swarm/dispatcher.py` and `alos/swarm/sandbox.py` retain zero third-party imports inside their module bodies per Specs 029 and 030; Hexagonal integration wraps them via outbound adapter classes.
