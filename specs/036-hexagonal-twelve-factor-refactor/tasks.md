# Tasks: Twelve-Factor, Pydantic v2, SOLID & Hexagonal Architecture Refactor

**Input**: `/specs/036-hexagonal-twelve-factor-refactor/` (`spec.md`, `plan.md`) and `docs/adr/0021*.md`..`0024*.md`

**Prerequisites**: `plan.md`, `spec.md`, `checklists/requirements.md`

**Tests & Docs**: Every PR (`200-395` LOC) enforces RED-first unit + `@mocked`/`@live` BDD tests, `100%` public docstrings (`audit-docstrings` == 0), updated inline design/ring comments, `0` `TODO/FIXME` markers, `CC <= 10`, and `>= 90%` coverage.

## Phase 1: Wave 0 Governance & AST Boundary Stack (`S0`: PR-01 -> PR-02)

- [x] T001 Record and accept MADR decisions `ADR-0021`..`ADR-0024` via `pyadr` in `docs/adr/` and `docs/adr/index.md` (`PR-01`)
- [x] T002 Author SpecKit 036 specification, 16-PR swarm plan, tasks, and requirements checklist in `specs/036-hexagonal-twelve-factor-refactor/` (`PR-02`)
- [x] T003 [P] Create Hexagonal ring package skeletons with architectural docstrings in `alos/{domain,application,adapters,config}/__init__.py` and smoke test `tests/meta/test_hexagonal_rings_exist.py` (`PR-01`)
- [x] T004 Implement AST inward-dependency boundary meta-test (`domain <- application <- adapters <- config`) in `tests/meta/test_hexagonal_boundaries.py` (`PR-02`)

## Phase 2: Wave 1 Settings, Stream Logging & Frozen Domain Models (`S1`: PR-03 -> PR-04 || PR-05)

**Goal (`[US1]`)**: Centralize `ALOSSettings` (`BaseSettings`), Factor XI `stdout`/`stderr` logging, and frozen Pydantic v2 domain models (`extra="forbid"`).

- [ ] T005 [P] [US1] Write failing `@mocked` and `@live` BDD scenarios (`# spec: 036-hexagonal-twelve-factor-refactor`) for `.env`/env resolution and stream logging in `tests/features/10_twelve_factor_config.feature` and `tests/step_defs/test_10_twelve_factor_config.py` (`PR-03`)
- [ ] T006 [US1] Declare `pydantic-settings>=2.0.0`, `pyyaml>=6.0.0`, and `alos = "alos.cli:main"` in `pyproject.toml`, implement `alos/config/{settings,logging}.py` with Factor III/XI docstrings, and wire shims in `alos/core/config.py`, `alos/crews/config.py`, `alos/db/session.py`, and `alembic/env.py` (`PR-03`)
- [ ] T007 [P] [US1] Write failing unit tests for frozen action union, `EmailSend`, `ContextPayload`, `UserProfile`, `RAGDocument`, and legacy schema shims in `tests/test_domain_action_context_models.py` (`PR-04`)
- [ ] T008 [P] [US1] Implement frozen `alos/domain/models/{actions,context,memory}.py` with schema invariant docstrings and re-export shims in `alos/schemas/actions.py` (`PR-04`)
- [ ] T009 [P] [US1] Write failing unit tests for `EvaluationResult`, `DecisionRecord`, `AuditEvent`, `N8nExecutionResponse`, and assignment-validated `SpanContext` in `tests/test_domain_provenance_models.py` (`PR-05`)
- [ ] T010 [P] [US1] Implement `alos/domain/models/{evaluation,audit,workflow,speckit,telemetry,crew}.py` with Constitutional Article I/III comments (`PR-05`)

## Phase 3: Wave 2 SOLID Policies, Segregated CQRS Ports & Approval Gate (`S2`: PR-06 -> PR-07 -> PR-08)

**Goal (`[US2]`)**: Replace closed `if/elif` rules with OCP registries, segregate read/write `Protocol` ports, and gate `RiskLevel.HIGH` on `HumanApprovalGatePort`.

- [ ] T011 [P] [US2] Write failing pure-domain unit tests for `RiskClassificationPolicy`, extensible `PolicyRuleRegistry`, `ActionDraftStrategyRegistry`, and `LifecycleFSM` in `tests/test_domain_policies.py` (`PR-06`)
- [ ] T012 [US2] Implement `alos/domain/services/{safety_policy,draft_builder,lifecycle_fsm}.py` (`CC <= 10`) with Strategy/Specification pattern docstrings (`PR-06`)
- [ ] T013 [P] [US2] Write failing protocol contract tests for `AssembleContextUseCase`, `PlanActionUseCase`, and `EvaluateActionUseCase` in `tests/test_application_core_use_cases.py` (`PR-07`)
- [ ] T014 [US2] Implement segregated CQRS ports in `alos/application/ports/{inbound,outbound}.py`, `alos/core/protocols.py` shim, and `alos/application/use_cases/{assemble_context,plan_action,evaluate_action}.py` (`PR-07`)
- [ ] T015 [P] [US2] Write failing `@mocked` and `@live` BDD scenarios for `HIGH`-risk `HumanApprovalGatePort` blocking vs `LOW`/`MEDIUM` autonomy in `tests/features/11_solid_approval_gate.feature` and `tests/step_defs/test_11_solid_approval_gate.py` (`PR-08`)
- [ ] T016 [US2] Implement `alos/application/use_cases/dual_loop_orchestrator.py` and documented Strangler-Fig shims in `alos/core/{context_assembler,planner,evaluator,graph}.py` (`PR-08`)

## Phase 4: Wave 3 Parallel Outbound Adapters Fan-Out (`PR-09 || PR-10 || PR-11 || PR-12` on `main`)

**Goal (`[US3]`)**: Migrate all driven infrastructure into disjoint `alos/adapters/outbound/*` packages concurrently with zero shared file touchpoints.

- [ ] T017 [P] [US3] Write failing `@mocked`/`@live` tests in `tests/test_adapter_vault_graph.py` and implement `alos/adapters/outbound/vault/{filesystem_vault,networkx_graph}.py` + `alos/memory/{obsidian_vault,obsidian_graph,brain_synthesizer}.py` shims (`PR-09`)
- [ ] T018 [P] [US3] Write failing LSP/parity tests in `tests/test_adapter_rag_native.py` and implement lazy-indexed `alos/adapters/outbound/{rag,native}/` (fixing `FallbackBM25Indexer` `0.0` non-match score) + `alos/memory/{vector_store,spec_rag}.py` and `alos/native/` shims (`PR-10`)
- [ ] T019 [P] [US3] Write failing restart-continuity and concurrency tests in `tests/test_adapter_audit_db.py` and implement `alos/adapters/outbound/{audit,db}/` (monotonic `D-NNN` recovery, file lock, `TelemetryTracer` lock, `SqlAlchemyUnitOfWork`, Postgres provenance adapters) + `alos/{logs,db}/` shims (`PR-11`)
- [ ] T020 [P] [US3] Write failing `@mocked` and loopback-HTTP `@live` tests in `tests/test_adapter_integrations_workflows.py` and implement `alos/adapters/outbound/{integrations,llm,speckit,swarm}/` + `alos/application/use_cases/{n8n_reflection_loop,crews,speckit_lifecycle}.py` + `alos/{integrations,engine/langgraph_n8n_loop,crews/crews}/` shims (`PR-12`)

## Phase 5: Wave 4 Bootstrap, Driving Adapters, Containers & Docs Suite (`S4`: PR-13 -> PR-14 -> PR-15 -> PR-16)

**Goal (`[US3]` & `[US4]`)**: Wire `BootstrapContainer`, inbound CLI/daemon/port-bound server, `SIGTERM` drain, hermetic containers, lint cleanup, and complete documentation/diagram refresh.

- [ ] T021 [P] [US3] Write failing CLI/CrewAI provenance tests in `tests/test_inbound_cli_and_bootstrap.py` and implement `alos/config/bootstrap.py`, `alos/adapters/inbound/{cli,crew_tools}.py` (`alos db`, `alos health`, `SafetyEvaluatorTool` -> `EvaluateActionUseCase`), and `alos/{cli,crews/tools}/` shims (`PR-13`)
- [ ] T022 [P] [US4] Write failing `@mocked` and `@live` `/healthz` + `SIGTERM` drain BDD scenarios in `tests/features/12_twelve_factor_lifecycle.feature` and `tests/step_defs/test_12_twelve_factor_lifecycle.py` (`PR-14`)
- [ ] T023 [US4] Implement `alos/adapters/inbound/{scheduler,health_mcp_server}.py` (`shutdown(wait=True)`, `dispose()`), stdlib `SIGTERM` traps in `alos/swarm/{dispatcher,sandbox}.py`, and `alos/engine/scheduler.py` shim (`PR-14`)
- [ ] T024 [US4] Harden `Dockerfile` and `Dockerfile.sandbox` (`uv sync --frozen --no-dev`, non-root, `HEALTHCHECK`), pin `docker-compose.yml` + `alos` service, remove `PLC0415`/`PLR0913`/`PLR0917` from `pyproject.toml`, and add `tests/test_container_manifests.py` (`PR-15`)
- [ ] T025 [US4] Rewrite `docs/architecture.md` (Hexagonal Mermaid diagrams, approval gate state machine, real ORM schemas), update `README.md` (First-ADE `A1/A8/A9` compliant), `docs/getting_started.md`, and `docs/specs_setup.md`, run `scripts/traceability.ps1` -> `docs/traceability.md`, and verify `tests/meta/test_docs_integrity.py` (`PR-16`)

## Dependencies & Swarm Parallelism Summary

- **Sequential GitHub Stacks** (child PRs opened `--draft --label wip` on parent branch, promoted via `git rebase --update-refs --onto origin/main`): `S0` (`PR-01 -> PR-02`), `S1` (`PR-03 -> PR-04 || PR-05`), `S2` (`PR-06 -> PR-07 -> PR-08`), `S4` (`PR-13 -> PR-14 -> PR-15 -> PR-16`).
- **Concurrent Multi-Worker Fan-Out**: `PR-04 || PR-05` (2 workers) and `PR-09 || PR-10 || PR-11 || PR-12` (4 workers in `workspace: "share"` directly targeting `main` with disjoint file sets).
