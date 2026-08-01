# Implementation Plan: Fix CI Pyadr Dependency

**Branch**: `001-fix-ci-pyadr` | **Date**: 2026-08-01 | **Spec**: [spec.md](file:///c:/Users/bfoxt/n8nSetup/specs/001-fix-ci-pyadr/spec.md)

## Summary

Add `pyadr>=0.16.2` to `pyproject.toml` under `[project.optional-dependencies] dev` and update `uv.lock` via `uv sync --extra dev` so that CI environment provisions `pyadr` executable during setup.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: pyadr, uv
**Testing**: pytest, ruff, mypy, bandit, pyadr check-adr-repo
**Target Platform**: Linux (GitHub Actions ubuntu-latest) / Windows (Local)

## Constitution Check

All quality gates compliant. Fix-first directive applied.

## Project Structure

```text
pyproject.toml
uv.lock
specs/001-fix-ci-pyadr/
├── spec.md
├── plan.md
└── tasks.md
```
