# Requirements Checklist: Fix All GitHub Issues

- [x] **FR-001**: System MUST update `.github/workflows/scheduled-matrix-test.yml` to use `uv sync --extra dev` and align the Python version matrix (`3.11`, `3.12`, `3.13`) with `pyproject.toml`'s `requires-python = ">=3.11"`.
- [x] **FR-002**: System MUST add Google-style docstrings to all public modules, classes, and functions in `alos/` currently flagged by the AST docstring audit, achieving 0 missing docstrings.
