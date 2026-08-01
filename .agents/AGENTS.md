# Project Agent Rules & Directives

This file contains repository-scoped behavioral rules and directives for AI agents working in this repository.

## Project Directives

### 1. Architectural Decision Records (ADRs)
- **Mandatory Tooling**: ALWAYS use the `pyadr` CLI for all ADR operations (`pyadr init`, `pyadr new`, `pyadr accept`, `pyadr reject`, `pyadr toc`, `pyadr check-adr-repo`).
- **Forbidden**: NEVER manually create or edit Markdown files directly inside `docs/adr/`.

### 2. Spec-Driven Development (SpecKit / SDD)
- **Specification Structure**: Features must follow the canonical SpecKit folder convention: `specs/<N>-<feature-name>/` containing `spec.md`, `plan.md`, `tasks.md`, and `checklists/requirements.md`.
- **Constitution**: System constitution directives live in `.specify/memory/constitution.md`.

### 3. Testing & TDD
- **Test-Driven Development**: Always follow Red-Green-Refactor. Write failing tests in `tests/test_sdd_bdd_features.py` before writing implementation code.
- **BDD Scenarios**: Gherkin acceptance feature files live in `tests/features/`.

### 4. Git Atomic Commit & Push Workflow
- **Commit Cadence**: "More is better". Commit early and often for every tested incremental change, decision, or spec milestone.
- **Skill Usage**: Refer to `.agents/skills/git-commit-and-push/SKILL.md` for explicit commit signing, staging isolation (never `git add .`), hygiene verification, conventional commit formatting, and pushing.

### 5. Git Tree History & Context Investigation
- **Git Tree as Primary Rationale Source**: The Git tree is a source of truth, history, and context. Use it to understand why code was written, evaluate legacy design choices, or analyze historical trends before making refactoring decisions or assumptions.
- **Skill Usage**: Refer to `.agents/skills/git-tree-context-search/SKILL.md` for querying git log history (`git log -S`, `git log -G`, `git log -p -L`, `git blame`, `git show`, `git log --grep`).

### 6. Code Quality, Rule Exception Documentation & Agent Fix-First Directive
- **Fix-First Directive (MANDATORY)**: AI agents MUST always prefer resolving and fixing code issues, bugs, linting errors, typing issues, security vulnerabilities, and Sonar code smells over ignoring or suppressing them (`# noqa`, `# type: ignore`, `NOSONAR`, `# pragma: no cover`), even if fixing is significantly harder or requires refactoring.
- **Mandatory Exception Documentation & Native Linter Enforcement**: Suppressions (`# noqa`, `# type: ignore`, `NOSONAR`, etc.) are permitted ONLY when fixing is technically impossible or limited by external framework requirements. Every exception MUST be preceded or accompanied by an explicit justification comment. Native linters strictly enforce rule specificity (`ruff` `PGH004` disallows bare `# noqa`, `RUF100` disallows unused `# noqa`, `mypy` `enable_error_code = ["ignore-without-code"]` disallows bare `# type: ignore`).
- **Sonar Scans & Quality Gates**: All code MUST pass Sonar code quality scans, ruff lint checks, mypy type checks, bandit security audits, and pytest suites. Pre-commit hooks run fast linting and formatting checks; pre-push hooks strictly enforce passing test suites, type checking, security audits, and Sonar quality gates.
