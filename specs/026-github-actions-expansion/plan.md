# Architecture & Implementation Plan: GitHub Actions Workflow Expansion

**Feature Branch**: `026-github-actions-expansion`
**Status**: Approved

---

## Technical Architecture & Component Matrix

```
.github/workflows/
├── quality-gate.yml               # Enhanced with uv lock --check & license audit
├── rust-ci.yml                    # Enhanced with cargo fmt --check & cargo audit
├── security-compliance.yml        # [NEW Group] Gitleaks, Scorecard, CodeQL
├── release-packaging.yml          # [NEW Group] Wheel build, Rust build, Docker buildx, SBOM
├── speckit-governance.yml         # [NEW Group] SpecKit completeness matrix & ADR audit
├── performance-benchmark.yml      # [NEW Group] Rust cargo bench & Python latency test
└── post-merge-pipeline.yml        # Consolidated post-merge analysis
```

---

## File Modification & Creation Matrix

1. **`specs/026-github-actions-expansion/`**:
   - `spec.md` (Feature requirements FR-001..FR-012)
   - `plan.md` (Architecture plan)
   - `tasks.md` (Implementation tasks)
   - `checklists/requirements.md` (Verification checklist)

2. **`.github/workflows/`**:
   - `security-compliance.yml` (NEW)
   - `release-packaging.yml` (NEW)
   - `speckit-governance.yml` (NEW)
   - `performance-benchmark.yml` (NEW)
   - `quality-gate.yml` (MODIFIED: uv lock check, license audit)
   - `rust-ci.yml` (MODIFIED: cargo fmt, cargo audit)

3. **`tests/`**:
   - `test_github_workflows.py` (NEW: Pytest suite checking all workflow YAML files)

---

## TDD Verification Strategy

1. Write `tests/test_github_workflows.py` first to assert existence and schema properties of all workflows.
2. Implement workflow files and enhancements.
3. Run `uv run pytest tests/test_github_workflows.py` to confirm GREEN.
4. Run `uv run ruff check alos tests` and `uv run mypy alos tests`.
