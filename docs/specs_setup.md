# Spec-Driven Development (SpecKit), ADRs, & Governance Workflow

> This document explains the **Spec-Driven Development (SpecKit / SDD)** methodology, Architectural Decision Record (ADR) governance, and Test-Driven Development (TDD/BDD) practices enforced in ALOS.

---

## 1. What is Spec-Driven Development (SDD)?

In traditional software development, developers frequently write code directly based on vague prompts or ambiguous tickets. This leads to scope creep, unverified assumptions, missing edge cases, and fragmented implementations.

**Spec-Driven Development (SDD)** flips this model: **No code is written until a comprehensive specification and execution plan are created, reviewed, and approved.**

In ALOS:
1. **The Specification is the Living Blueprint**: The files in `specs/` define the exact system behavior, functional requirements (`FR-XXX`), edge cases, and acceptance criteria.
2. **Code Traces Back to Specs**: Every class, function, and test in `alos/` explicitly cites its corresponding spec file (e.g., `Spec: specs/02-dual-loop-reasoning/spec.md`).
3. **Quality Gates Enforce Spec Compliance**: Automated tests and pre-push hooks verify that implementations fulfill every requirement defined in the spec.

---

## 2. Anatomy of a SpecKit Module (`specs/<N>-<feature-name>/`)

Every feature or capability module in ALOS lives inside `specs/<N>-<feature-name>/` and follows a standardized 4-part structure:

```
specs/02-dual-loop-reasoning/
├── spec.md                   # WHAT & WHY: User stories, functional requirements, acceptance criteria
├── plan.md                   # HOW: Architecture design, class contracts, data flow, file touchpoints
├── tasks.md                  # IMPLEMENTATION: Atomic, step-by-step checklist with task dependencies
└── checklists/
    └── requirements.md       # VALIDATION: Quality gate checklist verifying spec readiness
```

### Breakdown of Spec Files:

#### A. `spec.md` (The Requirement Contract)
Contains high-level context, target personas, user stories, and explicitly numbered Functional Requirements (`FR-001`, `FR-002`, ...):

```markdown
# Spec 02: Dual-Loop Reasoning Engine

## Functional Requirements
- **FR-001**: System MUST process prompts through a Fast Loop Planner and a Slow Loop Evaluator.
- **FR-002**: Evaluator MUST classify action risk into LOW, MEDIUM, or HIGH tiers.
- **FR-003**: Evaluator MUST emit a Decision Log ADR entry for every evaluation call.
```

#### B. `plan.md` (The Technical Blueprint)
Translates the requirements into concrete software architecture, component responsibility mappings (SOLID principles), Pydantic schemas, and file modifications.

#### C. `tasks.md` (The Execution Checklist)
Break down the implementation into small, ordered, atomic tasks:

```markdown
- [x] Task 1: Create `RiskLevel` Enum and `EvaluationResult` model in `alos/core/evaluator.py`.
- [x] Task 2: Implement `RiskClassifier.classify()` logic per Constitution Article V.
- [x] Task 3: Write failing unit test `tests/test_evaluator.py` for risk classification.
```

#### D. `checklists/requirements.md` (The Quality Gate)
A verification checklist completed before declaring a feature complete:
- [x] All unit and integration tests pass.
- [x] Zero mypy typing errors.
- [x] Decision log entries correctly emitted.

---

## 3. The Specification Index

ALOS capabilities are organized across 18 core specification modules:

| Spec Directory | Feature Domain | Key Technologies & Patterns |
| :--- | :--- | :--- |
| `specs/01-context-synthesis/` | Context Assembly & Synthesis | Profile loading, preference merging, RAG context |
| `specs/02-dual-loop-reasoning/` | Reasoning Engine | Fast Loop Planner, Slow Loop Evaluator, self-correction |
| `specs/03-safety-matrix/` | Safety Matrix & Risk Gates | LOW/MEDIUM/HIGH risk tiers, human consent gates |
| `specs/04-mcp-integrations/` | MCP Gateways & Protocol | Anthropic MCP, Google Calendar, Todoist, n8n webhooks |
| `specs/05-audit-and-decision-log/` | Decision Provenance & Audit | `logs/decision_log.jsonl`, `logs/system_audit.jsonl` |
| `specs/06-rag-and-knowledge-base/` | Vector Store & Local RAG | Hybrid BM25 + dense embeddings over markdown specs |
| `specs/07-postgres-orm-migrations/` | Database & ORM | SQLAlchemy 2.0 ORM, Alembic migrations, `pgvector` |
| `specs/08-obsidian-vault-brain-integration/` | Obsidian Vault Memory | Markdown vault engine, frontmatter parsing, NetworkX graph |
| `specs/09-core-frameworks-and-runtime/` | Core Frameworks | `pydantic-settings`, `tenacity`, `structlog`, `rich`, `typer` |
| `specs/10-database-and-orm-evolution/` | DB Evolution | `Mapped[T]`, `asyncpg` pooling, DuckDB, Polars |
| `specs/11-vector-store-and-rag-pipeline/` | Advanced RAG | LanceDB, ChromaDB, SentenceTransformers, RapidFuzz |
| `specs/12-agent-orchestration-and-state-graphs/` | Agent State Graphs | LangGraph state machine, `instructor`, FSM transitions |
| `specs/13-mcp-gateways-and-protocols/` | MCP Gateways | `fastmcp`, `httpx` async, `pybreaker` circuit breakers |
| `specs/14-observability-metrics-and-tracing/` | Observability & Tracing | OpenTelemetry, Prometheus metrics, Sentry SDK |
| `specs/15-testing-bdd-and-qa-automation/` | BDD & Testing | `pytest-bdd` Gherkin, `hypothesis` property testing |
| `specs/16-quality-gates-linting-and-security/` | Quality Gates | Ruff, Mypy strict mode, Bandit AST security scans |
| `specs/17-build-tooling-and-monorepo-workflow/` | Build Tooling | `uv` package manager, `pyadr` CLI, Docker multi-stage |
| `specs/18-architectural-patterns-and-cqrs/` | Design Patterns | CQRS, Event Bus, Repository Pattern, Strategy Pattern |

---

## 4. Architectural Decision Records (ADRs) with `pyadr`

All major architectural choices, component selections, and governance rules in ALOS are recorded as **Architectural Decision Records (ADRs)** inside `docs/adr/`.

> [!CAUTION]
> **STRICT RULE**: NEVER manually create or edit Markdown files inside `docs/adr/`. You MUST ALWAYS use the `pyadr` CLI tool for all ADR operations.

### Common `pyadr` CLI Workflows:

#### Propose a New ADR:
```powershell
uv run pyadr propose "Adopt LangGraph for Self-Reflection Loops"
```

#### Accept an ADR:
```powershell
uv run pyadr accept 10
```

#### Check ADR Repository Consistency:
```powershell
uv run pyadr check-adr-repo
```

ADRs provide an immutable, version-controlled history of **why** decisions were made, helping future developers understand legacy design choices without guesswork.

---

## 5. TDD & BDD Testing Workflow

ALOS strictly enforces **Test-Driven Development (TDD)** and **Behavior-Driven Development (BDD)**:

```
+------------------------------------------------------------------------------------+
|                               TDD & BDD CYCLE IN ALOS                              |
|                                                                                    |
|  1. Write Gherkin Feature    2. Write Failing Test     3. Implement Code           |
|     tests/features/*.feature    tests/test_sdd_*.py        alos/core/*.py          |
|     (Acceptance Scenario)       (Red Phase ❌)             (Green Phase ✅)        |
+------------------------------------------------------------------------------------+
```

### A. BDD Gherkin Feature Scenarios (`tests/features/`)
Acceptance criteria are written in plain Gherkin syntax:

```gherkin
Feature: Safety Matrix Evaluation
  Scenario: High risk action triggers human consent gate
    Given a proposed action of type "email_send"
    When the Evaluator node inspects the action
    Then the action risk level should be classified as "HIGH"
    And the evaluation result should require human approval
```

### B. Python Test Implementations (`tests/`)
Pytest steps match the Gherkin scenarios to verify software contracts. Run all tests with:

```powershell
uv run pytest
```

---

## 6. Code Quality & Fix-First Directive

In accordance with Constitution Article VII, ALOS enforces a strict **Fix-First Directive**:

1. **No Bare Suppressions**: Ignoring errors via bare `# noqa` or `# type: ignore` is strictly prohibited by linters (`ruff` `PGH004` and `mypy` `ignore-without-code`).
2. **Justification Mandatory**: If an exception is technically unavoidable due to an external library limitation, it MUST be accompanied by an explicit inline explanation comment.
3. **Pre-Push Gate**: Commits must pass Ruff, Mypy, Bandit, Pytest, and `pyadr` verification before pushing to Git.
