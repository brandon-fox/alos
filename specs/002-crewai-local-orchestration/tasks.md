# Tasks - 100% Local CrewAI Agents-as-Code Setup

**Feature Branch**: `002-crewai-local-orchestration`
**Spec Reference**: `specs/002-crewai-local-orchestration/spec.md`

## Sequential Implementation Tasks (TDD Cycle)

- [x] **Task 1: Spec & Plan Creation** (FR-002-01 .. FR-002-10)
  - Write `spec.md`, `plan.md`, `tasks.md` under `specs/002-crewai-local-orchestration/`.

- [x] **Task 2: Dependency Addition & Configuration Wrapper** (FR-002-01)
  - Add `crewai` to `pyproject.toml`.
  - Create `alos/crews/__init__.py` and `alos/crews/config.py` with `LocalLLMConfig` and `CREWAI_TELEMETRY_OPT_OUT`.

- [x] **Task 3: Custom Local Tools Implementation** (FR-002-04, FR-002-05, FR-002-06, FR-002-07)
  - Implement `ObsidianVaultTool` in `alos/crews/tools/obsidian_tool.py`.
  - Implement `SafetyEvaluatorTool` in `alos/crews/tools/evaluator_tool.py`.
  - Implement `MCPGatewayTool` in `alos/crews/tools/mcp_bridge_tool.py`.
  - Implement `N8nWorkflowTool` in `alos/crews/tools/n8n_tool.py`.

- [x] **Task 4: Declarative Configuration & CrewBase Classes** (FR-002-02, FR-002-03)
  - Create `alos/crews/config/agents.yaml` and `tasks.yaml`.
  - Implement `SpecKitArchitectCrew`, `CodeQualityCrew`, and `ObsidianGraphSynthesizerCrew` in `alos/crews/crews/`.

- [x] **Task 5: CLI Command Extension** (FR-002-08)
  - Add `alos crew run` command to `alos/cli.py`.

- [x] **Task 6: Pytest Suite & GitHub Actions Integration** (FR-002-09, FR-002-10)
  - Implement `tests/test_crewai_local.py` validating local configuration, tools, and crews.
  - Update `.github/workflows/quality-gate.yml` with `crewai-validation` job.

- [x] **Task 7: Quality Gates & Verification** (SC-001, SC-002, SC-003)
  - Run `uv run pytest tests/test_crewai_local.py`.
  - Run `uv run ruff check alos tests`, `uv run mypy alos`, `uv run bandit -r alos`.
