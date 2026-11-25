# Contributing to ALOS

ALOS follows **Spec-Driven Development (SpecKit)**, **Red-Green-Refactor TDD/BDD**, and **Trunk-Based Development** with cryptographically signed commits.

## 1. Branch Strategy & PR Size Discipline
- Branch from `main` using a standard prefix: `feat/`, `fix/`, `chore/`, `docs/`, `ci/`, `refactor/`, `test/`, `build/`, `perf/`, or `stack/`.
- Keep Pull Requests focused at **`200–400` non-lockfile lines** (`<= 1,000` hard CI ceiling). Use stacked Draft PRs (`--draft --label wip`) for larger initiatives.
- PR titles must follow **Conventional Commits** (`feat(scope): summary`) because `main` uses `PR_TITLE` squash merges to drive automated `release-please` SemVer releases.

## 2. SpecKit, ADRs & Testing Requirements
- Non-trivial features require a `specs/NNN-feature-name/` folder initialized via `.specify/scripts/powershell/create-new-feature.ps1` and architecture decisions recorded via `uv run pyadr new`.
- Write failing unit and `@mocked` + `@live` BDD tests before implementation (`>= 90%` dual-OS branch coverage).
- Fix lint/type/security issues at the root rather than suppressing them; any unavoidable `# noqa` or `# type: ignore[code]` requires an explicit justification comment.

## 3. Local Setup & Pre-Push Verification
```powershell
uv sync --extra dev
uv run pre-commit install --hook-type pre-commit --hook-type pre-push
uv run python scripts/run_validation_suite.py
uv run mkdocs build --strict
```
Ensure SSH or GPG commit signing (`commit.gpgsign=true`) is configured before committing; `main` enforces `required_signatures` and `ci-merge-gate`.
