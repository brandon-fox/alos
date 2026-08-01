# ALOS Git Workflow & Governance Guide

This document establishes the mandatory Git workflow, branch governance, commit signing, and code quality standards for the ALOS project.

---

## 1. Branching Strategy (Trunk-Based Development)

- **Primary Branch**: `main`
  - `main` is the single source of truth for production-ready code.
  - Commits directly to `main` are restricted. All changes must be delivered via dedicated feature/chore/fix branches and submitted via Pull Requests.

- **Branch Naming Conventions**:
  - `feat/<short-description>`: New system capabilities, integrations, or agents (e.g. `feat/context-rag`).
  - `fix/<issue-description>`: Bug fixes or system corrections (e.g. `fix/evaluator-schema-validation`).
  - `chore/<task-name>`: Tooling, dependency updates, or documentation updates (e.g. `chore/pre-commit-setup`).
  - `docs/<doc-name>`: Architectural documentation or spec updates.

---

## 2. Commit Signing Policy (Mandatory)

All commits in the ALOS codebase **MUST** have verified SSH or GPG signatures.

### SSH Signing Setup
1. Ensure your SSH key is added to Git configuration:
   ```bash
   git config --global gpg.format ssh
   git config --global user.signingkey ~/.ssh/id_ed25519.pub
   git config --global commit.gpgsign true
   ```
2. Verify commit signature:
   ```bash
   git log --show-signature -n 1
   ```

---

## 3. Git Isolation & Atomic Commits

To support concurrent AI agent operations and ensure atomic revision history:

- **STRICTLY FORBIDDEN**:
  - `git add .`
  - `git add -A`
  - `git commit -a`

- **MANDATORY**:
  - Explicitly stage ONLY the files modified for the specific task:
    ```bash
    git add alos/memory/spec_rag.py tests/test_spec_rag.py
    git commit -m "feat(rag): add spec-aware RAG indexer module"
    ```

---

## 4. Git Hygiene & Cache Prevention

- **Ignore Rules**:
  - Python byte-compiled artifacts (`**/__pycache__/`, `*.pyc`, `*.pycc`) MUST remain un-tracked.
  - Tooling cache folders (`.pytest_cache`, `.ruff_cache`, `.mypy_cache`) are strictly ignored in `.gitignore`.

- **Pre-Commit Verification**:
  - Always run `git status -s` and `git ls-files --others` before committing to verify zero unintended or cache files are staged.

---

## 5. Developer Tooling & Git Hooks

- **Pre-Commit Hooks** (`git commit`):
  - Trailing whitespace removal
  - YAML/JSON/TOML syntax checks
  - Private key & secret leak detection
  - `ruff` linting and formatting (`ruff check --fix`, `ruff format`)
  - Exception documentation validator (`check_exception_docs.py`)
  - Sonar code quality scan verification

- **Pre-Push Hooks** (`git push` - Strict Gate):
  - `bandit`: AST security vulnerability scan
  - `mypy`: Strict type check verification across codebase
  - `pytest`: All unit & integration tests must pass with coverage enforcement
  - `check-exception-docs`: Automated check ensuring zero undocumented `# noqa` or `# type: ignore` suppressions
  - `sonar-scanner`: Comprehensive Sonar code quality and bug / vulnerability gate audit

---

## 6. Code Quality, Exception Documentation & Agent Directives

- **Fix-First Mindset**: AI agents and developers must ALWAYS prioritize fixing bugs, lint warnings, type errors, and Sonar code smells over ignoring or suppressing them (`# noqa`, `# type: ignore`, `NOSONAR`), even when fixing is significantly harder.
- **Rule Exception Documentation**: Every inline suppression (e.g. `# noqa: F401`, `# type: ignore`) MUST be accompanied by an explicit inline or preceding technical justification comment. Undocumented suppressions will fail pre-commit and pre-push validation.

---

## 6. Development Workflow Quickstart

```powershell
# 1. Initialize dev environment and git hooks
.\.specify\scripts\powershell\setup-dev-environment.ps1
.\.specify\scripts\powershell\setup-git-workflow.ps1

# 2. Create feature branch off main
git checkout main
git pull upstream main
git checkout -b feat/my-feature

# 3. Code, test, and run pre-commit checks manually
uv run ruff check alos tests
uv run ruff format alos tests
uv run mypy alos
uv run bandit -r alos
uv run pytest

# 4. Explicitly stage and sign commit
git add <explicit-files>
git commit -m "feat(scope): descriptive commit message"

# 5. Push branch and open PR
git push origin feat/my-feature
```
