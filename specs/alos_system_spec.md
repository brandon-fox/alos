# ALOS System Specification — Cross-Reference Index

> ⚠️ **This file is a navigation index only.**
> The authoritative ALOS Constitution lives at [`.specify/memory/constitution.md`](../.specify/memory/constitution.md).
> Feature specifications live in `specs/NNN-<feature-name>/spec.md`.

---

## Canonical Specification & ADR Directory Index

| Spec Module | Domain / Title | Specification Path | Architectural Decision Record (ADR) |
| :--- | :--- | :--- | :--- |
| **Constitution** | Core System Governance | [`.specify/memory/constitution.md`](../.specify/memory/constitution.md) | [ADR 0000](../docs/adr/0000-record-architecture-decisions.md) |
| **Spec 001** | CI PyADR Verification & Health Gate | [`specs/001-fix-ci-pyadr/spec.md`](001-fix-ci-pyadr/spec.md) | [ADR 0001](../docs/adr/0001-use-markdown-architectural-decision-records.md) |
| **Spec 002** | CrewAI Local Orchestration | [`specs/002-crewai-local-orchestration/spec.md`](002-crewai-local-orchestration/spec.md) | N/A |
| **Spec 003** | Rust Core Architectural Refactor | [`specs/003-rust-core-architectural-refactor/spec.md`](003-rust-core-architectural-refactor/spec.md) | [ADR 0012](../docs/adr/0012-use-pyo3-and-maturin-for-rust-native-performance-extensions.md), [ADR 0013](../docs/adr/0013-adopt-rust-native-core-engine-and-pre-refactor-test-fortification-architecture.md) |
| **Spec 004** | Rust Native Performance Extensions | [`specs/004-rust-native-perf/spec.md`](004-rust-native-perf/spec.md) | [ADR 0012](../docs/adr/0012-use-pyo3-and-maturin-for-rust-native-performance-extensions.md) |
| **Spec 005** | Fix All GitHub Issues | [`specs/005-fix-all-github-issues/spec.md`](005-fix-all-github-issues/spec.md) | N/A |
| **Spec 006** | Context Synthesis | [`specs/006-context-synthesis/spec.md`](006-context-synthesis/spec.md) | N/A |
| **Spec 007** | Dual-Loop Reasoning | [`specs/007-dual-loop-reasoning/spec.md`](007-dual-loop-reasoning/spec.md) | [ADR 0004](../docs/adr/0004-implement-dual-loop-reasoning-core-with-safety-matrix-gate.md) |
| **Spec 008** | Safety Matrix Gate | [`specs/008-safety-matrix/spec.md`](008-safety-matrix/spec.md) | [ADR 0004](../docs/adr/0004-implement-dual-loop-reasoning-core-with-safety-matrix-gate.md) |
| **Spec 009** | MCP Integrations | [`specs/009-mcp-integrations/spec.md`](009-mcp-integrations/spec.md) | [ADR 0002](../docs/adr/0002-use-model-context-protocol-for-external-integrations.md) |
| **Spec 010** | Audit & Decision Log | [`specs/010-audit-and-decision-log/spec.md`](010-audit-and-decision-log/spec.md) | [ADR 0006](../docs/adr/0006-capture-runtime-action-decisions-with-decisionlogger-adr-records.md) |
| **Spec 011** | RAG & Knowledge Base | [`specs/011-rag-and-knowledge-base/spec.md`](011-rag-and-knowledge-base/spec.md) | [ADR 0003](../docs/adr/0003-adopt-local-obsidian-vault-and-vector-store-for-memory-rag.md) |
| **Spec 012** | PostgreSQL ORM & Migrations | [`specs/012-postgres-orm-migrations/spec.md`](012-postgres-orm-migrations/spec.md) | [ADR 0007](../docs/adr/0007-adopt-sqlalchemy-orm-and-alembic-for-postgresql-data-models-and-migrations.md) |
| **Spec 013** | Obsidian Vault Brain Integration | [`specs/013-obsidian-vault-brain-integration/spec.md`](013-obsidian-vault-brain-integration/spec.md) | [ADR 0008](../docs/adr/0008-integrate-obsidian-vault-brain-engine-into-alos-memory-architecture.md) |
| **Spec 014** | LangGraph n8n Self-Reflection | [`specs/014-langgraph-n8n-self-reflection/spec.md`](014-langgraph-n8n-self-reflection/spec.md) | [ADR 0010](../docs/adr/0010-adopt-langgraph-for-autonomous-self-reflection-loops-over-n8n-workflows.md) |
| **Spec 015** | Core Frameworks & Runtime | [`specs/015-core-frameworks-and-runtime/spec.md`](015-core-frameworks-and-runtime/spec.md) | [ADR 0009](../docs/adr/0009-adopt-open-source-dependencies-for-alos-core-architecture.md) |
| **Spec 016** | Database & ORM Evolution | [`specs/016-database-and-orm-evolution/spec.md`](016-database-and-orm-evolution/spec.md) | [ADR 0007](../docs/adr/0007-adopt-sqlalchemy-orm-and-alembic-for-postgresql-data-models-and-migrations.md) |
| **Spec 017** | Vector Store & RAG Pipeline | [`specs/017-vector-store-and-rag-pipeline/spec.md`](017-vector-store-and-rag-pipeline/spec.md) | [ADR 0003](../docs/adr/0003-adopt-local-obsidian-vault-and-vector-store-for-memory-rag.md) |
| **Spec 018** | Agent Orchestration & State | [`specs/018-agent-orchestration-and-state-graphs/spec.md`](018-agent-orchestration-and-state-graphs/spec.md) | [ADR 0010](../docs/adr/0010-adopt-langgraph-for-autonomous-self-reflection-loops-over-n8n-workflows.md) |
| **Spec 019** | MCP Gateways & Protocols | [`specs/019-mcp-gateways-and-protocols/spec.md`](019-mcp-gateways-and-protocols/spec.md) | [ADR 0002](../docs/adr/0002-use-model-context-protocol-for-external-integrations.md) |
| **Spec 020** | Observability & Tracing | [`specs/020-observability-metrics-and-tracing/spec.md`](020-observability-metrics-and-tracing/spec.md) | N/A |
| **Spec 021** | Testing & BDD Automation | [`specs/021-testing-bdd-and-qa-automation/spec.md`](021-testing-bdd-and-qa-automation/spec.md) | [ADR 0005](../docs/adr/0005-enforce-speckit-sdd-bdd-and-tdd-development-paradigms.md) |
| **Spec 022** | Quality Gates & Security | [`specs/022-quality-gates-linting-and-security/spec.md`](022-quality-gates-linting-and-security/spec.md) | N/A |
| **Spec 023** | Build Tooling & Monorepo | [`specs/023-build-tooling-and-monorepo-workflow/spec.md`](023-build-tooling-and-monorepo-workflow/spec.md) | [ADR 0005](../docs/adr/0005-enforce-speckit-sdd-bdd-and-tdd-development-paradigms.md) |
| **Spec 024** | Architectural Patterns & CQRS | [`specs/024-architectural-patterns-and-cqrs/spec.md`](024-architectural-patterns-and-cqrs/spec.md) | N/A |
| **Spec 025** | Open Source Dual Repo Architecture | [`specs/025-open-source-dual-repo-architecture/spec.md`](025-open-source-dual-repo-architecture/spec.md) | [ADR 0011](../docs/adr/0011-adopt-dual-repo-open-source-architecture-and-public-ci-cd-pipeline.md) |
| **Persona** | Executive Persona: Alex | [`specs/personas/alex_persona.md`](personas/alex_persona.md) | N/A |
