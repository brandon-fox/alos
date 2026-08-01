# Feature Specification: 100% Local CrewAI Agents-as-Code Setup for Antigravity Users

**Feature Branch**: `002-crewai-local-orchestration`
**Created**: 2026-08-01
**Status**: Approved
**Input**: 100% Local CrewAI Agents-as-Code Setup for Antigravity Users

## User Scenarios & Testing

### User Story 1 - Local-First Offline Agent Orchestration (Priority: P1)

As an Antigravity power user running ALOS locally, I want to execute multi-agent CrewAI tasks using local LLMs (Ollama/vLLM) without cloud API dependencies or telemetry data leakage.

**Why this priority**: Core system privacy and offline capability is the foundational requirement of ALOS.

**Independent Test**: Can be tested offline by configuring local Ollama backend and executing a CrewAI task, verifying zero outgoing network connections.

**Acceptance Scenarios**:
1. **Given** local Ollama is active (`http://localhost:11434`), **When** an agent task is triggered, **Then** CrewAI routes prompts to local models with `CREWAI_TELEMETRY_OPT_OUT=true`.
2. **Given** network is disconnected, **When** CrewAI tools run, **Then** local tools access local Obsidian vault files (`vault/`) and PostgreSQL without error.

---

### User Story 2 - Agents-as-Code & Declarative Configuration (Priority: P1)

As an ALOS developer, I want to define agents, tasks, tools, and crews strictly in standard Python code decorated with `@crew`, `@agent`, `@task`, paired with declarative YAML configurations.

**Why this priority**: Enables structured version control, static typing, and automated testing of multi-agent workflows.

**Independent Test**: Running `uv run pytest tests/test_crewai_local.py` validates declarative YAML loading, Pydantic action schema parsing, and CrewBase initialization.

**Acceptance Scenarios**:
1. **Given** `alos/crews/config/agents.yaml` and `tasks.yaml`, **When** `CrewBase` class initializes, **Then** agents and tasks are dynamically instantiated with proper tools and role definitions.

---

### User Story 3 - Antigravity Local Tools & Safety Matrix Enforcement (Priority: P2)

As a security-conscious user, I want CrewAI agent actions to be audited by the ALOS Deterministic Safety Matrix prior to tool execution.

**Why this priority**: Prevents autonomous agents from mutating critical files, running destructive shell commands, or making unauthorized database changes.

**Independent Test**: Invoking `SafetyEvaluatorTool` with a HIGH-risk action payload verifies that the evaluator returns a human approval requirement or blocks execution.

**Acceptance Scenarios**:
1. **Given** a HIGH-risk action proposal, **When** `SafetyEvaluatorTool` runs, **Then** action is evaluated against `.specify/memory/constitution.md` and flagged for human approval.
2. **Given** `ObsidianVaultTool` is invoked, **When** reading `vault/USER_PROFILE.md`, **Then** user preference context is injected into agent memory.

---

## Requirements

### Functional Requirements

- **FR-002-01**: System MUST provide a `LocalLLMConfig` wrapper supporting Ollama local endpoints (`http://localhost:11434`) and disabling telemetry (`CREWAI_TELEMETRY_OPT_OUT=true`).
- **FR-002-02**: System MUST define CrewAI agents as code using `@crew`, `@agent`, `@task`, and `@tool` decorators under `alos/crews/`.
- **FR-002-03**: System MUST provide declarative configuration files (`alos/crews/config/agents.yaml` and `tasks.yaml`).
- **FR-002-04**: System MUST provide `ObsidianVaultTool` to expose local Obsidian notes (`vault/`) as agent tools.
- **FR-002-05**: System MUST provide `SafetyEvaluatorTool` integrating `alos.engine.evaluator` to enforce Deterministic Safety Matrix risk gates.
- **FR-002-06**: System MUST provide `MCPGatewayTool` to bridge CrewAI tasks with Antigravity MCP servers.
- **FR-002-07**: System MUST provide `N8nWorkflowTool` to trigger local n8n workflows via `alos.integrations.n8n_client`.
- **FR-002-08**: System MUST provide a CLI entry point (`alos crew run --name <name>`) to invoke crews from terminal.
- **FR-002-09**: System MUST include a unit and integration test suite (`tests/test_crewai_local.py`) supporting offline mock LLM execution.
- **FR-002-10**: System MUST integrate `crewai-validation` into GitHub Actions Quality Gate ([`.github/workflows/quality-gate.yml`](file:///c:/Users/bfoxt/n8nSetup/.github/workflows/quality-gate.yml)).

---

## Success Criteria

- **SC-001**: 100% of unit tests pass with `uv run pytest tests/test_crewai_local.py`.
- **SC-002**: 100% compliance with `ruff check alos tests`, `mypy alos`, and `bandit -r alos`.
- **SC-003**: Zero cloud telemetry network requests during crew execution.
