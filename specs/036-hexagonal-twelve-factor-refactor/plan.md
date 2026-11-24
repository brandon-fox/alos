# Implementation Plan: Twelve-Factor, Pydantic v2, SOLID & Hexagonal Architecture Refactor

**Branch**: `hexagonal_architecture_refactor` (`036-hexagonal-twelve-factor-refactor`) | **Date**: 2026-11-24 | **Spec**: [spec.md](./spec.md)

**Input**: `specs/036-hexagonal-twelve-factor-refactor/spec.md` and ADRs [0021](../../docs/adr/0021-adopt-twelve-factor-application-alignment-and-constitutional-provenance-harmonization.md)-[0024](../../docs/adr/0024-adopt-hexagonal-ports-and-adapters-architecture-via-strangler-fig-incremental-prs.md).

## Summary

Transition ALOS to 100% Twelve-Factor alignment, centralized `pydantic-settings` (`ALOSSettings`), frozen Pydantic v2 domain models, SOLID policy/port abstractions, and a four-ring Hexagonal (Ports & Adapters) topology (`domain`, `application`, `adapters`, `config`). Designed for **autonomous overnight `/swarm` execution**, delivery is partitioned into **16 independently testable `200-395` line Pull Requests** (clearing the `400`-line soft limit and `1,000`-line hard ceiling of `pr-size-guard.yml`), combining **GitHub Stacked PR chains** (`S0`, `S1`, `S2`, `S4`) for sequential ring dependencies with **parallel direct-to-`main` fan-out** (`Wave 3`) across disjoint adapter packages, concluding with full architectural diagram, `README.md`, docstring, and design-comment synchronization.

## Technical Context

**Language/Version**: Python `>=3.11,<3.14` (CI 3.11-3.13; MyPy 3.12; Ruff `py310`) + Rust 2021 (`crates/alos_native` PyO3)
**Primary Dependencies**: `pydantic>=2.0`, `pydantic-settings>=2.0`, `pyyaml>=6.0`, `sqlalchemy>=2.0.52`, `alembic>=1.19.1`, `psycopg[binary]>=3.1`, `langgraph>=1.2.11`, `mcp>=1.0`, `apscheduler>=3.10`, `networkx>=3.0`, `rank-bm25>=0.2.2`, `python-frontmatter>=1.0`
**Storage**: Factor IV attached backing services -- Local Markdown Vault (`vault/`), append-only JSONL ledgers (`logs/decision_log.jsonl`, `logs/system_audit.jsonl`), and SQLAlchemy PostgreSQL/SQLite (`alos/adapters/outbound/db/`)
**Testing**: `pytest` (`<9.2.0`), `pytest-bdd` (`tests/features/` with `# spec: 036-hexagonal-twelve-factor-refactor`), `behave` (`features/`), `@mocked` + `@live` scenarios, `cargo test`
**Target Platform**: Windows 11 native host + Linux containers (`python:3.13-slim` via `uv sync --frozen`)
**Project Type**: Local-first autonomous CLI, background scheduler worker, and port-bound health/MCP service
**Performance Goals**: Sub-millisecond domain policy checks; lazy RAG index build on first query; `< 2.0s` `SIGTERM` drain
**Constraints**: Target `200-400` non-lockfile LOC/PR (`<= 1000` hard gate); AST `CC <= 10` (`<= 12` hard gate); coverage `>= 90%`; MyPy file precision `>= 75%`; `0` missing public docstrings; `0` `TODO/FIXME` markers; SSH-signed commits; `alos/swarm/{dispatcher,sandbox}.py` stdlib-only
**Scale/Scope**: 52+ Python modules, 4 ADRs (`0021`-`0024`), 16 incremental PRs across 5 `/swarm` waves

## Constitution Check

- **I. Determinism & Verification**: PASS -- Frozen Pydantic v2 models (`extra="forbid"`) + two-stage Plan -> Evaluate gate.
- **II. Local-First Privacy**: PASS -- Pure local Domain/Application; Vault isolated behind `VaultReaderPort`/`VaultWriterPort`.
- **III. Decision Provenance**: PASS -- Typed `DecisionRecord`/`AuditEvent`; CrewAI `SafetyEvaluatorTool` wired to `EvaluateActionUseCase`; monotonic `D-NNN` recovery.
- **IV. Test-First Development**: PASS -- Every `200-400` LOC PR commits RED unit + `@mocked`/`@live` BDD scenarios before implementation.
- **V. Safety Matrix Enforcement**: PASS -- Fixes `ALOSStateGraph.run()` bypass by gating `RiskLevel.HIGH` on `HumanApprovalGatePort` before `MCPGatewayPort`.
- **VI. Human-Centric Non-Intrusiveness**: PASS -- Stateless processes restoring from attached Vault/JSONL/DB backing services; clean `SIGTERM` drain.
- **VII. Code Quality & Fix-First**: PASS -- Eliminates `PLC0415`, `PLR0913`, and `PLR0917` root causes; enforces module/class/function docstrings and design comments.

## Project Structure (Target Hexagonal Rings + Strangler-Fig Shims)

```text
alos/
├── domain/                      # Ring 1: Pure Domain (stdlib + pydantic ONLY; zero I/O)
│   ├── models/                  # actions.py, context.py, memory.py, evaluation.py, audit.py, workflow.py, speckit.py, telemetry.py, crew.py
│   └── services/                # safety_policy.py, draft_builder.py, lifecycle_fsm.py
├── application/                 # Ring 2: Use Cases & Segregated CQRS Protocols
│   ├── ports/                   # inbound.py, outbound.py
│   └── use_cases/               # assemble_context.py, plan_action.py, evaluate_action.py, dual_loop_orchestrator.py, n8n_reflection_loop.py, crews.py, speckit_lifecycle.py
├── adapters/                    # Ring 3: Driving (Inbound) & Driven (Outbound) Adapters
│   ├── inbound/                 # cli.py, scheduler.py, crew_tools.py, health_mcp_server.py
│   └── outbound/                # vault/, rag/, native/, audit/, db/, integrations/, llm/, speckit/, swarm/
├── config/                      # Ring 4: Twelve-Factor Settings, Stream Logging & Composition Root
│   ├── settings.py              # ALOSSettings (pydantic-settings BaseSettings)
│   ├── logging.py               # Structured stdout/stderr event-stream configuration
│   └── bootstrap.py             # DI Container + SIGTERM/SIGINT graceful drain lifecycle
└── {core,schemas,logs,memory,integrations,db,engine,crews}/  # Thin __all__ Strangler-Fig re-export shims
```

## 16-PR Granular Stack & Wave Plan (`200-395` LOC / PR)

| PR | Branch | Stack / Base | Est. LOC | Independent Deliverable, Docs/Comments & Test Slice |
|---|---|---|---|---|
| **PR-01** | `docs/034-s0a-hexagonal-adrs` | `main` (Stack `S0` root) | ~285 | ADRs `0021`-`0024`, `docs/adr/index.md`, `alos/{domain,application,adapters,config}/__init__.py` ring docstrings + `tests/meta/test_hexagonal_rings_exist.py` |
| **PR-02** | `docs/034-s0b-speckit-034-ast-gate` | Stacked on `PR-01` | ~390 | `specs/036-*/*`, `.specify/feature.json`, AST ring-import boundary gate `tests/meta/test_hexagonal_boundaries.py` |
| **PR-03** | `feat/036-s1a-settings-and-logging` | Stacked on `PR-02` | ~340 | `pyproject.toml` (`pydantic-settings`, `pyyaml`), `ALOSSettings`, `logging.py`, config/DB/Alembic/runtime shims + `10_twelve_factor_config.feature` |
| **PR-04** | `refactor/036-s1b-action-context-models` | Stacked on `PR-03` (parallel w/ `05`) | ~320 | Frozen `actions.py` (`EmailSend`), `context.py` (`UserProfile`, `RAGDocument`), `memory.py`, `alos/schemas/` shims, schema docstrings + `test_domain_action_context_models.py` |
| **PR-05** | `refactor/036-s1c-provenance-workflow-models` | Stacked on `PR-03` (parallel w/ `04`) | ~310 | Frozen `evaluation.py`, `audit.py` (`DecisionRecord`, `AuditEvent`), `workflow.py`, `speckit.py`, `crew.py`, assignment-validated `telemetry.py` + `test_domain_provenance_models.py` |
| **PR-06** | `refactor/036-s2a-solid-domain-policies` | `main` (Stack `S2` root) | ~330 | `safety_policy.py` (`RiskClassificationPolicy`, OCP `PolicyRuleRegistry`), `draft_builder.py`, `lifecycle_fsm.py`, Strategy pattern comments + `test_domain_policies.py` |
| **PR-07** | `refactor/036-s2b-cqrs-ports-core-use-cases` | Stacked on `PR-06` | ~360 | `ports/{inbound,outbound}.py` (CQRS read/write split), `alos/core/protocols.py` shim, `{assemble_context,plan_action,evaluate_action}.py` + `test_application_core_use_cases.py` |
| **PR-08** | `feat/036-s2c-orchestrator-approval-gate` | Stacked on `PR-07` | ~350 | `dual_loop_orchestrator.py` (`HumanApprovalGatePort` gating `RiskLevel.HIGH`), `alos/core/{context_assembler,planner,evaluator,graph}.py` shims + `11_solid_approval_gate.feature` |
| **PR-09** | `refactor/036-w3a-vault-graph-adapters` | `main` (Wave 3 parallel) | ~320 | `adapters/outbound/vault/{filesystem_vault,networkx_graph}.py`, structured error logging, `alos/memory/obsidian_*` & `brain_synthesizer` shims + `test_adapter_vault_graph.py` |
| **PR-10** | `refactor/036-w3b-rag-native-adapters` | `main` (Wave 3 parallel) | ~340 | `adapters/outbound/{rag,native}/` (lazy BM25 build, `RAGDocument` LSP unification, fix `FallbackBM25Indexer` `0.0` non-match), shims + `test_adapter_rag_native.py` |
| **PR-11** | `refactor/036-w3c-audit-db-adapters` | `main` (Wave 3 parallel) | ~370 | `adapters/outbound/{audit,db}/` (monotonic `D-NNN` recovery, file lock, `TelemetryTracer` lock, `SqlAlchemyUnitOfWork`, Postgres provenance adapters), shims + `test_adapter_audit_db.py` |
| **PR-12** | `refactor/036-w3d-mcp-n8n-llm-adapters` | `main` (Wave 3 parallel) | ~380 | `adapters/outbound/{integrations,llm,speckit,swarm}/` (`N8nHttpAdapter` vs `N8nMockAdapter`, `MCPGatewayAdapter`, `OllamaLLMAdapter`), `{n8n_reflection_loop,crews,speckit_lifecycle}.py` + `test_adapter_integrations_workflows.py` |
| **PR-13** | `feat/036-s4a-bootstrap-cli-crew-tools` | `main` (Stack `S4` root) | ~360 | `config/bootstrap.py` DI container, `inbound/{cli,crew_tools}.py` (`alos db`, `alos health`, `SafetyEvaluatorTool` -> `EvaluateActionUseCase`), shims + `test_inbound_cli_and_bootstrap.py` |
| **PR-14** | `feat/036-s4b-server-scheduler-sigterm` | Stacked on `PR-13` | ~330 | `inbound/{scheduler,health_mcp_server}.py` (`/healthz`, `SIGTERM`/`SIGINT` `wait=True` drain, `dispose()`, stdlib `SIGTERM` traps in `alos/swarm/`) + `12_twelve_factor_lifecycle.feature` |
| **PR-15** | `chore/036-s4c-containers-lint-cleanup` | Stacked on `PR-14` | ~270 | Hermetic `Dockerfile*` (`uv sync --frozen --no-dev`, non-root), pinned `docker-compose.yml` + `alos` service, drop `PLC0415`/`PLR0913`/`PLR0917` from `pyproject.toml` + `test_container_manifests.py` |
| **PR-16** | `docs/036-s4d-diagrams-readme-traceability` | Stacked on `PR-15` | ~350 | Rewrite `docs/architecture.md` Mermaid diagrams & ORM docs, update `README.md` (First-ADE safe), `docs/getting_started.md`, `docs/specs_setup.md`, run `scripts/traceability.ps1`, mark `tasks.md` `[x]` + `test_docs_integrity.py` |

## Overnight `/swarm` Execution, GitHub Stack & CI Protocol

1. **Swarm Roster & Strict Disjoint File Ownership (`native_swarm` + `swarm_pane`)**:
   - **Coordinator**: Writes `.system_generated/swarm/plan.json` (4 outcome threads: `t-foundation`, `t-core-solid`, `t-adapters`, `t-runtime-docs`), spawns `monitor` (`swarm_monitor` skill), assigns slices by `@name`, references board context by `#seq`, and sleeps via `swarm_wait`.
   - **Authors (`workspace: "share"`)**: `author-foundation` (`PR-01..03`), `author-domain-a` (`PR-04, PR-06..08`), `author-domain-b` (`PR-05`), 4 concurrent Wave 3 workers (`adapter-vault` `PR-09`, `adapter-rag` `PR-10`, `adapter-audit-db` `PR-11`, `adapter-ext` `PR-12`), `author-runtime` (`PR-13..15`), and `author-docs` (`PR-16`). Never `kill` a `share` worker until its branch is pushed and merged on `origin/main`.
   - **Verifiers (`verifier-core`, `verifier-adapters`, `workspace: "inherit"`)**: Read-only gatekeepers verifying `200-400` LOC diff size, AST `CC <= 10`, `0` missing public docstrings, `0` `TODO/FIXME` markers, MyPy file precision `>= 75%`, isolated `--basetemp` `@mocked` + `@live` pytest `>= 90%` coverage, `behave --tags=-live`, and SSH commit signatures before handing off `#seq` to `@stack-shepherd`.
   - **Stack Shepherd (`stack-shepherd`, `workspace: "share"`)**: Sole agent permitted to `git push`, `gh pr create`, retarget stack bases, and rebase onto `origin/main`--eliminating multi-agent remote races.
2. **GitHub Stack Chaining & `auto-merge.yml` Safety Rule**:
   - Bottom PR (`A`) opens against `--base main` (ready for `auto-merge.yml` squash-merge once required checks pass).
   - Every stacked child PR (`B -> A`, `C -> B`) MUST open with `--base <parent-branch> --draft --label wip` so GitHub renders only the `200-400` LOC incremental diff AND `auto-merge.yml` never squashes `B` into `A`!
   - When `A` squash-merges into `main`, `stack-shepherd` runs `git fetch origin main && git rebase --update-refs --onto origin/main <old-A-sha> <top-branch>`, verifies SSH `gpgsig` headers (`First-ADE A7`), pushes `--force-with-lease`, and promotes `B` via `gh pr edit <PR-B> --base main --remove-label wip && gh pr ready <PR-B>` (triggering all `branches: [main]` CI workflows).
3. **Conflict, Dependabot & Post-Merge Bot Deconfliction**:
   - Spec `036` avoids unmerged stale drafts; hotspot files (`alos/cli.py`, `Dockerfile*`, `alos/swarm/`) are deferred to `PR-13..15`.
   - Ignore automated `chore/bot-changelog` and `chore/bot-coverage-gap` branches created by `post-merge-pipeline.yml`, fetching `origin/main` whenever they auto-merge.
