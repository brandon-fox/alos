# Feature Specification: Fix All GitHub Issues (Matrix Compatibility & Docstring Audit)

**Feature Branch**: `004-fix-all-github-issues`

**Created**: 2026-08-02

**Status**: Approved

**Input**: User description: "Fix all issues https://github.com/brandon-fox/alos/issues"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Matrix Test Workflow Compatibility Fix (Priority: P1)

As a maintainer, I need the automated scheduled matrix test GitHub workflow (`scheduled-matrix-test.yml`) to pass cleanly on all supported Python runtime versions (Python 3.11, 3.12, 3.13) so that automated issues #18, #19, and #20 are resolved and no false compatibility failure issues are created.

**Why this priority**: Continuous Integration matrix failures block release confidence and automatically generate issue noise.

**Independent Test**: Running the matrix workflow steps (`uv sync --extra dev` and `uv run pytest`) across Python 3.11 and 3.12 executes cleanly with 100% test pass rate.

**Acceptance Scenarios**:

1. **Given** the `scheduled-matrix-test.yml` workflow, **When** matrix testing executes on supported Python versions (3.11, 3.12, 3.13), **Then** all test dependencies are synchronized via `uv sync --extra dev` and pytest executes without collection or dependency errors.
2. **Given** open issues #18, #19, and #20, **When** matrix tests pass cleanly, **Then** the open compatibility issues are closed on GitHub.

---

### User Story 2 - Complete Docstring Audit Compliance (Priority: P1)

As a maintainer, I need all public modules, classes, and functions across the `alos` package to have comprehensive docstrings so that AST docstring audits pass with zero missing docstrings.

**Why this priority**: Docstring completeness is mandatory for code maintainability, automated API documentation generation, and post-merge audit compliance (Issue #6).

**Independent Test**: Running the AST docstring audit script returns a count of `0` missing docstrings across `alos/`.

**Acceptance Scenarios**:

1. **Given** any public module, class, or function in `alos/`, **When** the AST docstring audit script inspects `alos/`, **Then** every public symbol has a valid non-empty docstring.
2. **Given** open issue #6, **When** all 82+ missing docstrings are added and verified, **Then** issue #6 is closed.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST update `.github/workflows/scheduled-matrix-test.yml` to use `uv sync --extra dev` and align the Python version matrix (`3.11`, `3.12`, `3.13`) with `pyproject.toml`'s `requires-python = ">=3.11"`.
- **FR-002**: System MUST add Google-style docstrings to all public modules, classes, and functions in `alos/` currently flagged by the AST docstring audit, achieving 0 missing docstrings.

### Key Entities

- **AST Docstring Audit**: Python AST analyzer (`doc_audit.py`) that checks for module, class, and function docstrings on public symbols in `alos/`.
- **Scheduled Matrix Test Workflow**: GitHub Actions workflow (`scheduled-matrix-test.yml`) executing multi-version Python compatibility matrix checks.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `doc_audit.py` returns `Count: 0` missing docstrings across all Python files in `alos/`.
- **SC-002**: `uv run pytest` passes 100% of unit tests.
- **SC-003**: `uv run ruff check alos tests` and `uv run mypy alos` pass with zero lint or type errors.
- **SC-004**: All open GitHub issues (#6, #18, #19, #20) are closed via GitHub MCP.

## Assumptions

- Python runtime target is Python >= 3.11 as defined in `pyproject.toml`.
- Docstrings must follow Google style guidelines and preserve existing signatures and type annotations without code behavior changes.
