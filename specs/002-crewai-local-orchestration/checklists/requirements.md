# Quality Gate & Compliance Checklist: 002-crewai-local-orchestration

- [x] **FR-002-01**: System MUST provide a `LocalLLMConfig` wrapper supporting Ollama local endpoints (`http://localhost:11434`) and disabling telemetry (`CREWAI_TELEMETRY_OPT_OUT=true`).
- [x] **FR-002-02**: System MUST define CrewAI agents as code using `@crew`, `@agent`, `@task`, and `@tool` decorators under `alos/crews/`.
- [x] **FR-002-03**: System MUST provide declarative configuration files (`alos/crews/config/agents.yaml` and `tasks.yaml`).
- [x] **FR-002-04**: System MUST provide `ObsidianVaultTool` to expose local Obsidian notes (`vault/`) as agent tools.
- [x] **FR-002-05**: System MUST provide `SafetyEvaluatorTool` integrating `alos.engine.evaluator` to enforce Deterministic Safety Matrix risk gates.
- [x] **FR-002-06**: System MUST provide `MCPGatewayTool` to bridge CrewAI tasks with Antigravity MCP servers.
- [x] **FR-002-07**: System MUST provide `N8nWorkflowTool` to trigger local n8n workflows via `alos.integrations.n8n_client`.
- [x] **FR-002-08**: System MUST provide a CLI entry point (`alos crew run --name <name>`) to invoke crews from terminal.
- [x] **FR-002-09**: System MUST include a unit and integration test suite (`tests/test_crewai_local.py`) supporting offline mock LLM execution.
- [x] **FR-002-10**: System MUST integrate `crewai-validation` into GitHub Actions Quality Gate ([`.github/workflows/quality-gate.yml`](file:///c:/Users/bfoxt/n8nSetup/.github/workflows/quality-gate.yml)).
