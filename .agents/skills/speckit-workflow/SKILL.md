---
name: speckit-workflow
description: Strictly enforced Spec-Driven Development (SpecKit / SDD) workflow. Ensures feature creation, spec drafting, architecture planning, task breakdowns, and requirement checklists are strictly executed via `.specify/scripts/powershell/` before any implementation code is written.
---

# SpecKit / Spec-Driven Development (SDD) Workflow Skill

This skill enforces strict compliance with SpecKit / Spec-Driven Development (SDD) workflows across the ALOS repository.

> [!IMPORTANT]
> **STRICT DIRECTIVE**: AI agents MUST NOT write or modify implementation code without an active, fully defined SpecKit feature directory under `specs/<N>-<feature-name>/`. Shortcuts, skipping spec documentation, or diving directly into coding without following the SDD cycle are strictly forbidden.

---

## 1. Canonical SpecKit Directory Structure

Every system feature, capability, refactoring effort, or architectural modification MUST reside inside a dedicated SpecKit folder following this exact structure:

```
specs/<N>-<feature-name>/
├── spec.md              # What & Why: User stories, acceptance criteria, FR-XXX requirements
├── plan.md              # How: Component architecture, API contracts, data models, source layout
├── tasks.md             # Implementation Plan: Atomic, sequential TDD tasks with checkboxes
└── checklists/
    └── requirements.md  # Quality gate & compliance validation checklist
```

The system constitution directives in `.specify/memory/constitution.md` serve as the overarching governance model for all specifications.

---

## 2. Mandatory SDD Workflow Steps

### Step 1: Feature Branch & Folder Initialization
Use the official PowerShell script to bootstrap a new feature branch and directory structure:

```powershell
.\.specify\scripts\powershell\create-new-feature.ps1 -ShortName "<short-feature-name>" "<Detailed Feature Description>"
```

- This auto-increments the feature number (`001`, `002`, etc.) or uses timestamping.
- It creates `specs/<N>-<short-feature-name>/spec.md` populated from `.specify/templates/spec-template.md`.
- It sets `.specify/feature.json` so downstream scripts automatically locate the active feature.

### Step 2: Specification Draft (`spec.md`)
Edit `specs/<N>-<feature-name>/spec.md` to define:
- **User Stories & Scenarios**: Plain-language description of desired behaviors.
- **Functional Requirements (`FR-001`, `FR-002`, ...)**: Explicit, unambiguous requirements.
- **Acceptance Criteria & Gherkin Scenarios**: Concrete BDD Given-When-Then scenarios.
- **Non-Functional Requirements**: Performance, security, privacy, and local-first constraints.

### Step 3: Architectural Plan & Checklist (`plan.md` & `checklists/requirements.md`)
Run the setup plan script to initialize the architectural plan and requirement validation checklist:

```powershell
.\.specify\scripts\powershell\setup-plan.ps1
```

Edit `specs/<N>-<feature-name>/plan.md` to document:
- **Technical Architecture & Data Models**: Pydantic v2 schemas and system boundaries.
- **Module & File Layout**: Exact files to create or modify.
- **TDD Test Strategy**: Unit tests and BDD acceptance test mappings (`tests/features/`).
- **Constitution Gate Validation**: Compliance check against `.specify/memory/constitution.md`.

Verify that `specs/<N>-<feature-name>/checklists/requirements.md` accurately lists all FR-XXX acceptance criteria.

### Step 4: Atomic Task Breakdown (`tasks.md`)
Run the setup tasks script to initialize the task checklist:

```powershell
.\.specify\scripts\powershell\setup-tasks.ps1
```

Edit `specs/<N>-<feature-name>/tasks.md` to structure execution into ordered, atomic tasks:
- Task 1: Write BDD acceptance tests (`tests/features/<feature>.feature`) and pytest suite (`tests/test_<feature>.py`) — **Verify RED (failing)**.
- Task 2..N: Implement code modules iteratively — **Verify GREEN (passing)**.
- Task N+1: Code quality audit (Ruff lint, Mypy typing, Bandit security, Sonar scan) & Refactor.
- Task N+2: Update Architectural Decision Records (`pyadr`) if architectural decisions were made.

### Step 5: TDD Execution & Requirement Tracing
- Execute implementation strictly in the order defined in `tasks.md`.
- Check off completed tasks (`- [x] Task description`) as work progresses.
- Ensure every line of added or modified code traces back to an explicit requirement (`FR-XXX`) in `spec.md`.

---

## 3. Strict Compliance Guidelines for AI Assistants

1. **No Code Before Spec**: Never generate implementation code before creating `spec.md`, `plan.md`, `tasks.md`, and `checklists/requirements.md`.
2. **Use PowerShell Helper Scripts**: Always execute `.specify/scripts/powershell/create-new-feature.ps1`, `setup-plan.ps1`, and `setup-tasks.ps1` for directory and template management.
3. **Constitution Governance**: All plans and specifications must respect the core principles of `.specify/memory/constitution.md` (Local-first, TDD, Decision provenance, Safety matrix, Fix-first directive).
4. **Git Hygiene & Atomic Commits**: Commit early and often for each completed SpecKit milestone using signed commits and explicit file staging (`git add <file>`). Refer to `git-commit-and-push` skill.
5. **Quality Gates**: Ensure code passes `ruff check`, `mypy`, `bandit`, `pytest`, and Sonar quality scans prior to finalizing the feature.
