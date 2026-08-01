# Feature Specification: Fix CI Pyadr Dependency

**Feature Branch**: `001-fix-ci-pyadr`

**Created**: 2026-08-01

**Status**: Active

**Input**: User description: "Fix missing pyadr dependency in CI workflow (Run 30714547525)"

## User Scenarios & Testing

### User Story 1 - CI Pipeline Execution (Priority: P1)

As a contributor to ALOS, I want GitHub Actions CI to have all required development CLI dependencies (`pyadr`) installed during `uv sync --extra dev` so that the ADR Repository Governance quality gate step succeeds.

**Why this priority**: Continuous Integration must pass green for PRs and pushes to main.

**Independent Test**: Execute `uv sync --extra dev` followed by `uv run pyadr check-adr-repo` in a clean Python environment.

**Acceptance Scenarios**:

1. **Given** a fresh Python 3.12 environment with `uv`, **When** `uv sync --extra dev` is run, **Then** `pyadr` binary is installed in `.venv` and `uv run pyadr check-adr-repo` completes successfully with exit code 0.

## Requirements

### Functional Requirements

- **FR-001**: `pyproject.toml` MUST declare `pyadr` under `[project.optional-dependencies] dev`.
- **FR-002**: `uv.lock` MUST lock a valid version of `pyadr` (`>=0.16.2`).
- **FR-003**: `uv run pyadr check-adr-repo` MUST execute successfully during CI governance verification.

## Success Criteria

### Measurable Outcomes

- **SC-001**: GitHub Actions workflow run passes all steps in `test-and-lint` job including `Verify ADR Repository Governance`.
- **SC-002**: Local quality checks (`pyadr`, `ruff`, `mypy`, `pytest`) all pass without errors.
