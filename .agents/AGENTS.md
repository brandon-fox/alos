# Project Agent Rules & Directives

This file contains repository-scoped behavioral rules and directives for AI agents working in this repository.

## Project Directives

### 1. Architectural Decision Records (ADRs)
- **Mandatory Tooling**: ALWAYS use the `pyadr` CLI for all ADR operations (`pyadr init`, `pyadr new`, `pyadr accept`, `pyadr reject`, `pyadr toc`, `pyadr check-adr-repo`).
- **Forbidden**: NEVER manually create or edit Markdown files directly inside `docs/adr/`.

### 2. Spec-Driven Development (SpecKit / SDD)
- **Mandatory Workflow & Skill (STRICT ENFORCEMENT)**: AI agents MUST NEVER bypass, skip, or ignore SpecKit workflows. No implementation code may be written or modified without an active, approved feature directory under `specs/<N>-<feature-name>/`.
- **Specification Structure**: Features must follow the canonical SpecKit folder convention: `specs/<N>-<feature-name>/` containing `spec.md`, `plan.md`, `tasks.md`, and `checklists/requirements.md`.
- **Constitution**: System constitution directives live in `.specify/memory/constitution.md`.
- **Skill Usage**: Refer to `.agents/skills/speckit-workflow/SKILL.md` for explicit PowerShell script invocation (`create-new-feature.ps1`, `setup-plan.ps1`, `setup-tasks.ps1`), requirement tracing (`FR-XXX`), and TDD phase enforcement.

### 3. Testing & TDD
- **Test-Driven Development**: Always follow Red-Green-Refactor. Write failing tests in `tests/test_sdd_bdd_features.py` before writing implementation code.
- **BDD Scenarios**: Gherkin acceptance feature files live in `tests/features/`.

### 4. Git Atomic Commit, Push & Worktree Lifecycle Workflow
- **Commit Cadence**: "More is better". Commit early and often for every tested incremental change, decision, or spec milestone.
- **Mandatory PR & Worktree Lifecycle**: Every worktree or feature branch task MUST conclude with creating a Pull Request (`gh pr create` or `create_pull_request`). Agents MUST monitor the PR state until merged, and clean up the worktree (`git worktree remove`) and branch (`git branch -d`) after merge confirmation.
- **Skill Usage**: Refer to `.agents/skills/git-commit-and-push/SKILL.md` for explicit commit signing, staging isolation (never `git add .`), hygiene verification, PR creation, status monitoring, and worktree cleanup.

### 5. Git Tree History & Context Investigation
- **Git Tree as Primary Rationale Source**: The Git tree is a source of truth, history, and context. Use it to understand why code was written, evaluate legacy design choices, or analyze historical trends before making refactoring decisions or assumptions.
- **Skill Usage**: Refer to `.agents/skills/git-tree-context-search/SKILL.md` for querying git log history (`git log -S`, `git log -G`, `git log -p -L`, `git blame`, `git show`, `git log --grep`).

### 6. Code Quality, Rule Exception Documentation & Agent Fix-First Directive
- **Fix-First Directive (MANDATORY)**: AI agents MUST always prefer resolving and fixing code issues, bugs, linting errors, typing issues, security vulnerabilities, and Sonar code smells over ignoring or suppressing them (`# noqa`, `# type: ignore`, `NOSONAR`, `# pragma: no cover`), even if fixing is significantly harder or requires refactoring.
- **Mandatory Exception Documentation & Native Linter Enforcement**: Suppressions (`# noqa`, `# type: ignore`, `NOSONAR`, etc.) are permitted ONLY when fixing is technically impossible or limited by external framework requirements. Every exception MUST be preceded or accompanied by an explicit justification comment. Native linters strictly enforce rule specificity (`ruff` `PGH004` disallows bare `# noqa`, `RUF100` disallows unused `# noqa`, `mypy` `enable_error_code = ["ignore-without-code"]` disallows bare `# type: ignore`).
- **Sonar Scans & Quality Gates**: All code MUST pass Sonar code quality scans, ruff lint checks, mypy type checks, bandit security audits, and pytest suites. Pre-commit hooks run fast linting and formatting checks; pre-push hooks strictly enforce passing test suites, type checking, security audits, and Sonar quality gates.

### 7. Subagent Delegation Protocol & Adaptive Workspace Rules
- **Proactive Delegation**: AI agents MUST spawn specialized subagents (`invoke_subagent` or `define_subagent`) for parallel research, heavy context searching, code quality audits, and test execution.
- **Risk-Adaptive Workspaces**:
  - `Workspace: inherit` (Shared Workspace): Use for low-risk, non-destructive, or read-only subtasks (e.g. running test suites, querying git history, reading documentation, auditing code quality).
  - `Workspace: branch` (Isolated Workspace): Use for high-risk or structural refactoring, major architectural changes, and experimental feature branches.
- **Worktree Teardown**: Upon task completion, subagents in branched workspaces MUST ensure changes are pushed, a Pull Request is opened, monitored until merged, and the branched worktree directory is safely unmounted and deleted.
- **Skill Usage**: Refer to `.agents/skills/agentic-autonomy/SKILL.md` for guidance on subagent composition and background task orchestration.

### 8. Tooling Autonomy, Proactive Permissions & Non-Blocking Execution
- **Proactive Permission Elevation**: At session start or when introducing new CLI tools, agents MUST request broad command prefix grants using `ask_permission` (e.g. `Action: command`, `Target: "uv"`, `Target: "git"`, `Target: "docker"`, `Target: "pyadr"`, `Target: "pre-commit"`) to eliminate interactive user prompts for safe tool execution.
- **Asynchronous Execution & Scheduling**: Long-running operations (test suites, container spinups, quality audits) MUST be executed as non-blocking background tasks (`run_command` async or `schedule` timers), enabling parallel execution without blocking interaction.
