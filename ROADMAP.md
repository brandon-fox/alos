# ALOS Architectural Roadmap & Capability Expansion

## Executive Overview
This roadmap establishes a multi-phase engineering plan to eliminate custom reimplementations, modernize the ALOS software architecture, and achieve enterprise-grade stability, observability, and agentic autonomy.

All 100 architectural enhancement ideas are codified into **10 canonical SpecKit modules** (`specs/015-` through `specs/024-`). Each module provides detailed specifications (`spec.md`), technical execution plans (`plan.md`), task checklists (`tasks.md`), and quality gate requirements (`checklists/requirements.md`).

---

## Strategic Phases & Spec Mapping

```mermaid
gantt
    title ALOS Strategic Implementation Roadmap
    dateFormat  YYYY-MM-DD
    section Phase I: Core & Runtime
    015 Core Frameworks & Runtime       :2026-08-01, 30d
    016 Database & ORM Evolution        :2026-08-15, 30d
    022 Quality Gates & Security        :2026-08-01, 45d
    section Phase II: Memory & Agents
    017 Vector Store & RAG Pipeline     :2026-09-01, 30d
    018 Agent Orchestration & LangGraph :2026-09-15, 30d
    019 MCP Gateways & Protocols        :2026-09-15, 30d
    section Phase III: Observability & QA
    020 Observability & Tracing         :2026-10-01, 30d
    021 Testing & BDD Automation        :2026-10-15, 30d
    section Phase IV: Tooling & Patterns
    023 Build Tooling & Monorepo        :2026-11-01, 30d
    024 Architectural Patterns & CQRS   :2026-11-15, 30d
```

---

## Specification Directory Index

| Spec Module | Domain Area | Target Technologies & Core Patterns | Spec Directory |
| :--- | :--- | :--- | :--- |
| **Spec 015** | Core Frameworks & Runtime | `pydantic-settings`, `tenacity`, `structlog`, `rich`, `diskcache`, `cachetools`, `humanize`, `dependency-injector`, `typer` | [`specs/015-core-frameworks-and-runtime/`](specs/015-core-frameworks-and-runtime/) |
| **Spec 016** | Database & ORM Evolution | SQLAlchemy 2.0 `Mapped[T]`, `alembic autogen`, `pgvector`, `asyncpg` pooling, `duckdb`, `polars` | [`specs/016-database-and-orm-evolution/`](specs/016-database-and-orm-evolution/) |
| **Spec 017** | Vector Store & RAG Pipeline | `lancedb`, `chromadb`, `sentence-transformers`, `rapidfuzz`, `tiktoken`, hybrid BM25+dense RRF | [`specs/017-vector-store-and-rag-pipeline/`](specs/017-vector-store-and-rag-pipeline/) |
| **Spec 018** | Agent Orchestration & State | `langgraph` state machines, `instructor` structured outputs, `temporalio`, `transitions` FSM | [`specs/018-agent-orchestration-and-state-graphs/`](specs/018-agent-orchestration-and-state-graphs/) |
| **Spec 019** | MCP Gateways & Protocols | Official Anthropic `mcp` SDK, `fastmcp`, `httpx` async, `pybreaker` circuit breakers, Authlib OAuth2 | [`specs/019-mcp-gateways-and-protocols/`](specs/019-mcp-gateways-and-protocols/) |
| **Spec 020** | Observability & Tracing | OpenTelemetry SDK, `prometheus_client`, `loguru`, `sentry-sdk`, DB audit triggers | [`specs/020-observability-metrics-and-tracing/`](specs/020-observability-metrics-and-tracing/) |
| **Spec 021** | Testing & BDD Automation | `pytest-bdd` Gherkin, `hypothesis` property testing, `time-machine`, `vcrpy`, `factory_boy` | [`specs/021-testing-bdd-and-qa-automation/`](specs/021-testing-bdd-and-qa-automation/) |
| **Spec 022** | Quality Gates & Security | Ruff (`UP`, `B`, `SIM`), Mypy strict mode, `pre-commit` hooks, SonarQube, `bandit` AST scans | [`specs/022-quality-gates-linting-and-security/`](specs/022-quality-gates-linting-and-security/) |
| **Spec 023** | Build Tooling & Monorepo | `uv` package manager, `pyproject.toml` workspaces, `pyadr` CLI, multi-stage Docker | [`specs/023-build-tooling-and-monorepo-workflow/`](specs/023-build-tooling-and-monorepo-workflow/) |
| **Spec 024** | Architectural Patterns | CQRS, Event Bus, Repository Pattern, Strategy Pattern, Saga Pattern, Null Object Pattern | [`specs/024-architectural-patterns-and-cqrs/`](specs/024-architectural-patterns-and-cqrs/) |

---

## Quality & Acceptance Gates

All roadmap implementations must satisfy the following strict quality criteria before merging into `main`:
1. **SpecKit Completeness**: Each feature must contain matching `spec.md`, `plan.md`, `tasks.md`, and `checklists/requirements.md`.
2. **ADR Record Verification**: Major architectural transitions must be recorded using `uv run pyadr propose` and `accept`.
3. **100% Test Passing Rate**: Full unit and integration suites must pass via `.\.venv\Scripts\pytest.exe`.
4. **Zero Linting & Typing Errors**: Code must pass `uv run ruff check alos` and `uv run mypy alos`.
5. **Signed Git Isolation**: All commits must be signed (`git commit -S`) with isolated explicit file staging.
