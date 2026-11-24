# Implementation Tasks: Automatic Signed PR Rebase & Universal Auto-Merge

**Spec**: [`spec.md`](spec.md)

- [x] **Task 1**: Initialize SpecKit `033-automatic-signed-pr-rebase` and accept `ADR-0017` via `pyadr`.
- [x] **Task 2**: Author failing BDD (`automatic_signed_pr_rebase.feature`) and pytest (`test_signed_pr_rebase.py`, `test_github_workflows.py`) suites (RED).
- [x] **Task 3**: Create `.github/actions/setup-git-signing/action.yml` and `.github/scripts/signed_pr_rebase.py`.
- [x] **Task 4**: Update `auto-merge.yml`, `ade-axioms.yml`, `post-merge-pipeline.yml`, and `setup-git-workflow.ps1`.
- [x] **Task 5**: Verify `pytest`, `ruff`, `mypy`, `bandit`, and `pyadr check-adr-repo` (GREEN), commit signed, and open PR.
