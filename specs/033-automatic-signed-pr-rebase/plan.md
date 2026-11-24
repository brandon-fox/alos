# Technical Execution Plan: Automatic Signed PR Rebase & Universal Auto-Merge

**Spec**: [`spec.md`](spec.md) | **ADR**: [ADR-0017](../../docs/adr/0017-adopt-signed-ci-pr-rebase-and-universal-auto-merge.md)

## Components

- `.github/actions/setup-git-signing/action.yml`: Composite action configuring `gpg.format=ssh`, derived `.pub` `user.signingkey`, `commit.gpgsign=true`, and `tag.gpgsign=true` from `COMMIT_SIGNING_KEY`.
- `.github/scripts/signed_pr_rebase.py`: Typed CLI (`--mode single|queue`) checking `merge-base --is-ancestor` and `gpgsig` headers, executing `git rebase --force-rebase origin/main`, aborting cleanly on conflicts, and force-pushing with lease.
- `.github/workflows/auto-merge.yml`: Universal auto-merge (`automerge`), per-PR `signed-rebase-on-update`, and serialized `rebase-queue` + 30-min cron sweep with isolated concurrency groups.
- `.github/workflows/ade-axioms.yml`: Preserves pinned First-ADE validator and prints unsigned commit diagnostics on failure.
- `.github/workflows/post-merge-pipeline.yml`: Wires `./.github/actions/setup-git-signing` and `PR_QUEUE_TOKEN || GITHUB_TOKEN` into `generate-changelog` and `coverage-gap`.
- `.specify/scripts/powershell/setup-git-workflow.ps1`: Enforces local `commit.gpgsign=true` and `tag.gpgsign=true`.
