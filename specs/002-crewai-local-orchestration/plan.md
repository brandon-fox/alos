# Implementation Plan - 100% Local CrewAI Agents-as-Code Setup

**Feature Branch**: `002-crewai-local-orchestration`
**Spec Reference**: `specs/002-crewai-local-orchestration/spec.md`

## Technical Architecture & Module Structure

```
alos/
├── crews/
│   ├── __init__.py
│   ├── config.py             # Local Ollama LLM config & CREWAI_TELEMETRY_OPT_OUT
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── obsidian_tool.py  # ObsidianVaultTool for vault/ reading
│   │   ├── evaluator_tool.py # SafetyEvaluatorTool wrapping alos.engine.evaluator
│   │   ├── mcp_bridge_tool.py# MCPGatewayTool bridging Antigravity MCP servers
│   │   └── n8n_tool.py       # N8nWorkflowTool for n8n trigger execution
│   ├── crews/
│   │   ├── __init__.py
│   │   ├── speckit_architect_crew.py
│   │   ├── code_quality_crew.py
│   │   └── obsidian_graph_crew.py
│   └── config/
│       ├── agents.yaml
│       └── tasks.yaml
```

## Component Details

1. **`LocalLLMConfig` (`alos/crews/config.py`)**:
   - Disables telemetry (`os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"`).
   - Wraps local Ollama base URL (`http://localhost:11434`) and model defaults (`ollama/qwen2.5-coder:32b`, `ollama/llama3.1:8b`).
   - Supports offline mock LLM mode for unit tests.

2. **Custom Local Tools (`alos/crews/tools/`)**:
   - `ObsidianVaultTool`: Searches/reads notes from `vault/` to inform agent context.
   - `SafetyEvaluatorTool`: Evaluates proposed actions using `alos.engine.evaluator` and assigns LOW/MED/HIGH risk.
   - `MCPGatewayTool`: Bridges Antigravity MCP server tools.
   - `N8nWorkflowTool`: Triggers local n8n workflows via `alos.integrations.n8n_client`.

3. **Agents as Code (`alos/crews/crews/`)**:
   - `SpecKitArchitectCrew`: Generates BDD spec files.
   - `CodeQualityCrew`: Runs linting, typing, security, and pytest checks with fix-first suggestions.
   - `ObsidianGraphSynthesizerCrew`: Synthesizes user daily notes into knowledge graph links.

4. **CLI Integration (`alos/cli.py`)**:
   - Adds `alos crew run --name <crew_name>` command.

5. **GitHub Actions Integration (`.github/workflows/quality-gate.yml`)**:
   - Adds `crewai-validation` job to run `pytest tests/test_crewai_local.py` in CI.
