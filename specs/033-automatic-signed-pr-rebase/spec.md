# Feature Specification: Automatic Signed PR Rebase & Universal Auto-Merge

**Feature Branch**: `automatic_rebase_pr_workflow` (`033-automatic-signed-pr-rebase`) | **Status**: Active

## Intent

Ensure every PR in `brandon-fox/alos` automatically gets squash auto-merge enabled, stays rebased onto `main` on every update (PR updates, `main` pushes, and scheduled sweeps), and satisfies First-ADE Axiom A7 (`gpgsig` header on every commit) across rebase, merge, and bot commits.

## Requirements

- **FR-001**: `auto-merge.yml` MUST mark non-hold (`wip`, `do-not-merge`) Drafts ready, approve Dependabot, and enable `--auto --squash` via `PR_QUEUE_TOKEN || GITHUB_TOKEN`.
- **FR-002**: On `pull_request` updates, `auto-merge.yml` MUST run `signed_pr_rebase.py --mode single` via `setup-git-signing` when behind or unsigned.
- **FR-003**: On `push`, `schedule`, and `workflow_dispatch`, `auto-merge.yml` MUST run `--mode queue` and sweep open PRs.
- **FR-004**: `auto-merge.yml` MUST isolate concurrency per PR / `check_run` SHA / queue ref.
- **FR-005**: `setup-git-signing` MUST configure SSH signing from `COMMIT_SIGNING_KEY`; `post-merge-pipeline.yml` and `setup-git-workflow.ps1` MUST enforce signing.
- **FR-006**: `ade-axioms.yml` MUST run First-ADE validator and print unsigned commit diagnostics on failure.
- **FR-007**: All external actions MUST use 40-char SHAs with version comments and `timeout-minutes` 1..60.
- **SC-001**: `pytest` (`test_github_workflows.py`, `test_signed_pr_rebase.py`, `test_automatic_signed_pr_rebase.py`), `ruff`, `mypy`, `bandit`, and `pyadr check-adr-repo` pass.
