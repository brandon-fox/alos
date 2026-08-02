# ALOS — Local Autonomous Life Operating System

> **ALOS** is a local-first, privacy-focused autonomous AI Life Operating System built with Python 3.10+, Pydantic v2, LangGraph, SQLAlchemy 2.0, and local Spec-Driven RAG architecture.

---

## 📚 Human Documentation Index

Explore our comprehensive, human-readable documentation suite:

| Document | Topic & Focus |
| :--- | :--- |
| 💡 [**The Core Idea & Philosophy**](file:///c:/Users/bfoxt/n8nSetup/docs/idea.md) | Vision, data sovereignty, Dual-Loop reasoning, Safety Matrix, and local Obsidian vault memory. |
| 🚀 [**Getting Started Guide**](file:///c:/Users/bfoxt/n8nSetup/docs/getting_started.md) | Prerequisites, `uv` installation, PowerShell setup scripts, Docker PostgreSQL, and CLI usage. |
| 🏗️ [**Architecture Deep Dive**](file:///c:/Users/bfoxt/n8nSetup/docs/architecture.md) | Technical blueprint, LangGraph state machine, Evaluator safety gate, Obsidian brain, and MCP gateways. |
| 📋 [**Spec-Driven Development (SpecKit)**](file:///c:/Users/bfoxt/n8nSetup/docs/specs_setup.md) | SpecKit structure (`spec.md`, `plan.md`, `tasks.md`), `pyadr` ADR management, and TDD/BDD workflow. |
| 🤖 [**Agents vs Gemini Customization Guide**](file:///c:/Users/bfoxt/n8nSetup/docs/agents_vs_gemini_guide.md) | Architectural comparison between `.agents/` workspace rules and `.gemini/` global skills. |
| 🐰 [**CodeRabbit AI Integration Guide**](file:///c:/Users/bfoxt/n8nSetup/docs/CODERABBIT_GUIDE.md) | How to use CodeRabbit AI reviews, custom repository directives, and slash commands in PRs. |

---

## ⚡ Quick Start

```powershell
# 1. Install dependencies with uv
uv sync --extra dev

# 2. Run automated environment setup
.\.specify\scripts\powershell\setup-dev-environment.ps1
.\.specify\scripts\powershell\setup-git-workflow.ps1

# 3. Spin up PostgreSQL + pgvector
docker compose up -d

# 4. Run full test suite & quality gates
uv run pytest
uv run ruff check alos tests
uv run mypy alos tests
```

---

## 🔑 Key Features & Architecture

```
+-----------------------------------------------------------------------------------+
|                                 ALOS CORE ENGINE                                  |
|                                                                                   |
|  1. LOCAL DATA SOVEREIGNTY    2. DUAL-LOOP REASONING     3. SAFETY MATRIX GATE    |
|  Local embeddings, local RAG  Fast Planner Loop +        LOW / MED / HIGH risk    |
|  Obsidian markdown vault      Slow Evaluator Loop        Human approval gates     |
|                                                                                   |
|  4. OBSIDIAN VAULT MEMORY     5. LANGGRAPH STATE         6. MCP & N8N INTEGRATION |
|  USER_PROFILE, PREFERENCES,   Self-reflection loops      Anthropic MCP gateways   |
|  CORRECTION_LEDGER            deterministic transitions  n8n automation client    |
+-----------------------------------------------------------------------------------+
```

- **Local-First Privacy**: Your notes, calendar events, and preferences never leave your machine.
- **Dual-Loop Reason-Before-Act Engine**: Proposed actions undergo deterministic evaluation before execution.
- **Deterministic Safety Matrix**: Actions are assigned fail-safe risk levels; high-risk mutations require human consent.
- **Obsidian Vault Memory**: System memory is stored in plain Markdown files (`vault/`) that you can read and edit anytime.
- **Spec-Driven Governance**: 100% of features trace back to canonical specifications in `specs/`.

---

## 🌐 Open Source & Dual-Repo Architecture

ALOS uses a **Dual-Repository Architecture** to separate the open-source core framework from your private user setup:

```
+-------------------------------------------------------+
|  PUBLIC GITHUB REPO (alos)                            |
|  - alos/ (LangGraph engine, Evaluator, SCHEMAS)       |
|  - vault.example/ (Sample template profiles)          |
|  - workflows.example/ (Sample n8n JSON templates)     |
|  - .github/workflows/ci.yml (Free GitHub Actions)    |
|  - LICENSE (MIT License) & .env.example               |
+-------------------------------------------------------+
                           ▲
                           │ (Import / Dependency / Volume Mount)
                           ▼
+-------------------------------------------------------+
|  PRIVATE GITHUB REPO (my-alos-workspace)              |
|  - .env (Private secrets, API keys, tunnel tokens)    |
|  - my-vault/ (Your real Obsidian notes & daily logs)  |
|  - my-workflows/ (Your real n8n JSON exports)        |
|  - docker-compose.override.yml (Volume mounts)        |
+-------------------------------------------------------+
```

* **Public Core Repo (`alos`)**: Contains the core Python package, LangGraph state graph, baseline n8n JSON templates (`workflows.example/`), and Obsidian vault templates (`vault.example/`).
* **Private Workspace Repo (`my-alos-workspace`)**: Keep your actual `.env` secrets, production n8n workflows, and personal Obsidian vault notes in a private VCS repository.

---

## 🧪 Testing & Governance

- **Continuous Integration**: GitHub Actions CI workflow ([`.github/workflows/ci.yml`](file:///c:/Users/bfoxt/n8nSetup/.github/workflows/ci.yml)) runs test suites and quality gates on every push/PR.
- **Constitution**: The immutable system law lives at [`.specify/memory/constitution.md`](file:///c:/Users/bfoxt/n8nSetup/.specify/memory/constitution.md).
- **ADRs**: Architectural Decision Records are stored in [`docs/adr/`](file:///c:/Users/bfoxt/n8nSetup/docs/adr/) and managed strictly via the `pyadr` CLI (ADR-0011 covers Dual-Repo Architecture).
- **TDD / BDD**: Acceptance feature files live in [`tests/features/`](file:///c:/Users/bfoxt/n8nSetup/tests/features/).

---

## 📄 License & Maintainers

Distributed under the **MIT License**. See [`LICENSE`](file:///c:/Users/bfoxt/n8nSetup/LICENSE) for details.

Built with ❤️ by the ALOS Engineering Team. Built for local privacy, autonomy, and developer joy.
