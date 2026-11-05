# alos

> **Status:** active, pre-release (0.1.0), single maintainer. Core engine, safety matrix, vault memory and migrations run; the n8n and MCP integrations are scaffolds. Not yet packaged for anyone but its author.

ALOS (Local Autonomous Life Operating System) is a local-first autonomous agent runtime. It plans and evaluates actions in two loops, scores every proposed action against a deterministic safety matrix before anything executes, and keeps its memory in a plain-Markdown Obsidian vault on your machine. Python 3.11+, Pydantic v2, LangGraph, SQLAlchemy 2.0, PostgreSQL + pgvector, with a Rust native crate for the hot paths.

It is built spec-first: every feature traces to a `spec.md`, `plan.md` and `tasks.md` under [`specs/`](specs/), architecture decisions are recorded with `pyadr` under [`docs/adr/`](docs/adr/), and acceptance scenarios are Gherkin feature files under [`tests/features/`](tests/features/). The current trace table, including the gaps, is [`docs/traceability.md`](docs/traceability.md).

## Documentation

| Document | Covers |
| :--- | :--- |
| [The core idea](docs/idea.md) | Data sovereignty, dual-loop reasoning, the safety matrix, vault memory. |
| [Getting started](docs/getting_started.md) | Prerequisites, `uv`, PowerShell setup scripts, Docker PostgreSQL, CLI usage. |
| [Architecture](docs/architecture.md) | LangGraph state machine, the evaluator gate, the Obsidian brain, MCP gateways. |
| [Spec-driven development](docs/specs_setup.md) | SpecKit layout, `pyadr` ADR management, TDD/BDD workflow. |
| [Agents vs Gemini customization](docs/agents_vs_gemini_guide.md) | `.agents/` workspace rules compared with `.gemini/` global skills. |
| [CodeRabbit integration](docs/CODERABBIT_GUIDE.md) | Review directives and slash commands used in pull requests. |

## Quick start

```powershell
# 1. Install dependencies with uv
uv sync --extra dev

# 2. Run automated environment setup
.\.specify\scripts\powershell\setup-dev-environment.ps1
.\.specify\scripts\powershell\setup-git-workflow.ps1

# 3. Spin up PostgreSQL + pgvector
docker compose up -d

# 4. Run the test suite and quality gates
uv run pytest
uv run ruff check alos tests
uv run mypy alos tests
```

## What it does

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
|  CORRECTION_LEDGER            deterministic transitions  n8n automation client   |
+-----------------------------------------------------------------------------------+
```

- **Local-first.** Notes, calendar events and preferences never leave the machine.
- **Reason before act.** A proposed action passes the evaluator loop before it executes.
- **Deterministic safety matrix.** Every action gets a risk level; high-risk mutations wait for human consent.
- **Vault memory.** System memory is Markdown under `vault/` that you can read and edit at any time.
- **Spec-driven governance.** Features trace to specifications; see the trace table for what does and does not yet.

## Open source, dual-repo layout

The public core (this repository) is separated from a private workspace so nothing personal ships:

```
+-------------------------------------------------------+
|  PUBLIC REPOSITORY (alos)                              |
|  - alos/ (LangGraph engine, evaluator, schemas)        |
|  - crates/alos_native (Rust acceleration via PyO3)     |
|  - vault.example/ (template profiles)                  |
|  - workflows.example/ (template n8n JSON)              |
|  - .github/workflows/ (quality gate, release, security)|
+-------------------------------------------------------+
                           ^
                           | import / dependency / volume mount
                           v
+-------------------------------------------------------+
|  PRIVATE REPOSITORY (my-alos-workspace)                |
|  - .env (secrets, API keys, tunnel tokens)             |
|  - my-vault/ (real Obsidian notes and daily logs)      |
|  - my-workflows/ (real n8n exports)                    |
|  - docker-compose.override.yml (volume mounts)         |
+-------------------------------------------------------+
```

## Governance

- **Constitution.** The system law lives at [`.specify/memory/constitution.md`](.specify/memory/constitution.md); every agent action and state transition must comply with it. ADR-0011 records the dual-repository decision.
- **Quality gate.** [`quality-gate.yml`](.github/workflows/quality-gate.yml) runs uv lock check, ruff, mypy, bandit, pytest, ADR governance, dependency review, Docker validation and CrewAI validation on every push and pull request. [`rust-ci.yml`](.github/workflows/rust-ci.yml) builds the native crate.
- **Axioms.** The First-ADE axioms (license holder, independence, honest status, signed commits, conflict markers, workflow integrity) run via [`ade-axioms.yml`](.github/workflows/ade-axioms.yml).
- **ADRs and specs.** [`docs/adr/`](docs/adr/) via `pyadr`; [`specs/`](specs/) via SpecKit; [`docs/traceability.md`](docs/traceability.md) maps one to the other.

## License and author

MIT License, copyright Brandon Fox. See [`LICENSE`](LICENSE). To cite, see [`CITATION.cff`](CITATION.cff).

## Independence

This is a personal project by Brandon Fox, built on my own time and equipment. It is not affiliated with, endorsed by, or derived from the work of any employer, current or former, and does not represent their views, products or practices. Licensed under the MIT License; principles at [First-ADE/PRINCIPLES.md](https://github.com/First-ADE/.github/blob/main/PRINCIPLES.md).
