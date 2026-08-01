# Tasks: Fix CI Pyadr Dependency

- [x] Task 1: Add `pyadr>=0.16.2` to `pyproject.toml` under `[project.optional-dependencies] dev`
- [x] Task 2: Sync dependencies and update `uv.lock` via `uv sync --extra dev`
- [x] Task 3: Verify local governance check (`uv run pyadr check-adr-repo`)
- [x] Task 4: Verify local quality gates (`ruff`, `mypy`, `pytest`)
- [ ] Task 5: Commit changes and push branch to GitHub
