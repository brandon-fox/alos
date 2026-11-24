# Consolidate CI Workflows into Cached Groups Behind Unified Merge Gate and Declarative Rulesets

* Status: accepted
* Deciders: Brandon Fox
* Date: 2026-11-24

Technical Story: `specs/038-enterprise-cicd-pipeline/spec.md`

## Context and Problem Statement

ALOS's GitHub Actions pipeline has grown to 18 separate workflow files spawning 26+ virtual machines per pull request while leaving `main` under-protected:
1. **Sprawl & Duplicate VM Overhead**: `uv-lock-check`, `ruff-lint`, `mypy-types`, `bandit-security`, `adr-governance`, `speckit-governance.yml`, `code-review-bot.yml`, `spec-analyzer-bot.yml`, and `crewai-validation` each boot separate runners and sync 218 Python packages independently (~3.5 minutes of VM startup overhead for `< 15s` of static checks), while `post-merge-pipeline.yml` runs `pytest` twice more.
2. **Bypassable Ruleset & Security Theater**: Live `Ruleset 20200177` requires only 6 path-filtered August-2026 checks, leaving 14+ checks (`pytest-windows`, `combined-coverage`, `qa-deep-fanout`, `Rust`, `sandbox`, `ADE axioms`, `PR title`, `gitleaks`) unrequired; `dependency-review` and `gitleaks-scan` use `continue-on-error: true`; fork PRs fail on unguarded write-token steps; and `auto-merge.yml` fires `check_run` cascade storms while promoting Draft PRs via `gh pr ready` before CI passes.
3. **Single-Maintainer vs. Non-Human Review Nuance**: Because GitHub prohibits self-approval by a single contributor (`@brandon-fox`), `main` cannot set `required_approving_review_count: 1` globally today without blocking human PRs, yet non-human PRs require `1` approval and onboarding a second human collaborator must trigger an immediate elevation to `1` required review.

How should ALOS achieve fast, DRY, zero-bypass CI and `main`/tag protection at scale without custom code sprawl?

## Decision Drivers

* **Reuse over Rebuild**: Leverage `brandon-fox/.github` (`setup-uv-cached`, `setup-rust-cached`, `cache-ml-weights`, `pr-size-guard.yml`, `links-check.yml`, `ci-autofix.yml`), `First-ADE/ade-axioms`, and proven upstream actions instead of custom Python packages in `alos/`.
* **Speed via Grouping & Multi-Layer Caching**: Collapse single-command VMs into 7 grouped workflows sharing warm checkouts, cached `uv` envs, `.mypy_cache`/`.ruff_cache`, `Swatinem/rust-cache` (`Cargo.lock`), `sccache`, and scope-isolated BuildKit GHA layer caches.
* **Zero-Bypass Merge, Draft & Review Governance**: Expose one terminal `ci-merge-gate` (`pull_request`, `merge_group`, `push`), gate Draft `gh pr ready` promotion on `workflow_run` `CI` success, enforce `1` approval on non-human PRs, alert via `sync_github_governance.py --check` when `collaborators > 1`, and codify `main` + `v*` tag rulesets in `.github/rulesets/*.json`.

## Considered Options

* Option 1: Consolidate 18 workflows into 7 cached, grouped pipelines reusing upstream actions behind a terminal `ci-merge-gate` + `workflow_run`-gated Draft promotion + non-human `1`-approval & collaborator sentinel + declarative `.github/rulesets/*.json`
* Option 2: Build a custom Hexagonal `alos/domain/cicd` Python framework while keeping 18+ separate workflow files
* Option 3: Keep individual ungrouped jobs and manually list 20+ status check names in the GitHub UI ruleset

## Decision Outcome

Chosen option: "Option 1: Consolidate 18 workflows into 7 cached, grouped pipelines reusing upstream actions behind a terminal `ci-merge-gate` + `workflow_run`-gated Draft promotion + non-human `1`-approval & collaborator sentinel + declarative `.github/rulesets/*.json`", because grouping fast static/governance checks cuts per-PR VM spawns by >50% (`< 15s` warm static lane), reusing upstream actions keeps `alos/` 100% bloat-free, and a single `ci-merge-gate` plus declarative rulesets and collaborator monitoring closes every branch-protection, fork-PR, and Draft-promotion gap.

### Positive Consequences

* Shrinks `.github/workflows/` from 18 files to **7** clear pipelines (`quality-gate`, `pr-automation`, `security-compliance`, `release-please`, `release-packaging`, `nightly-health`, `post-merge-pipeline`).
* Eliminates `check_run` cascade storms and premature Draft PR promotion while enforcing `1` approval on non-human PRs and alerting automatically when a second human contributor is added.
* Enforces `required_signatures`, `required_linear_history`, `required_review_thread_resolution`, `PR_TITLE` squash headers, `sha_pinning_required: true`, `90%` coverage, and immutable `refs/tags/v*` tags via versioned JSON specs.

### Negative Consequences

* Initial ruleset cutover (`sync_github_governance.py --apply`) must run immediately after `PR-03` merges `ci-merge-gate` onto `main` so in-flight PRs never wait on a non-existent check.

## Pros and Cons of the Options

### Option 1: Consolidated 7-Workflow Suite + Upstream Actions + `ci-merge-gate` + Declarative Rulesets

* Good, because cuts runner boot overhead by >50% and shares `.mypy_cache`, `.ruff_cache`, `rust-cache`, `sccache`, and scoped BuildKit caches.
* Good, because adds zero CI framework bloat to `alos/` (~95-line `sync_github_governance.py` is the only helper script).
* Bad, because requires updating `tests/test_github_workflows.py` to assert the consolidated 7-workflow layout instead of legacy sprawl filenames.

### Option 2: Custom `alos/domain/cicd` Python CI framework + 18 separate workflows

* Good, because exercises Hexagonal patterns on CI logic.
* Bad, because reinvents `release-please`, `labeler`, and `semantic-pull-request` in bespoke Python code while leaving 26+ slow VM boots per PR untouched.

### Option 3: Ungrouped jobs listed manually in GitHub UI rulesets

* Good, because requires minimal workflow restructuring.
* Bad, because wastes runner minutes on redundant `uv sync` setups, deadlocks on workflow `paths:` filters, and drifts silently in the UI.

## Links

* Refines [ADR-0011](0011-adopt-dual-repo-open-source-architecture-and-public-ci-cd-pipeline.md)
* Preserves [ADR-0017](0017-adopt-signed-ci-pr-rebase-and-universal-auto-merge.md), [ADR-0020](0020-adopt-property-fuzzing-differential-native-verification-mutation-testing-and-dual-os-coverage-matrix.md), and [ADR-0024](0024-adopt-hexagonal-ports-and-adapters-architecture-via-strangler-fig-incremental-prs.md)
