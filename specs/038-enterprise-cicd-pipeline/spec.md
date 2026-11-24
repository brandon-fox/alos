# Feature Specification: Enterprise-Grade DRY Open-Source CI/CD, Vetted PR Drafts, Main Protection & Automated Release Pipeline

**Feature Branch**: `enterprise_grade_cicd_pipeline` (`038-enterprise-cicd-pipeline`)

**Created**: 2026-11-24

**Status**: Approved for Incremental PR Execution

**Architecture Decisions**: [ADR-0026](../../docs/adr/0026-consolidate-ci-workflows-into-cached-groups-behind-unified-merge-gate-and-declarative-rulesets.md), [ADR-0027](../../docs/adr/0027-adopt-release-please-maturin-sccache-and-github-oidc-slsa-provenance-over-custom-release-scripts.md)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consolidated High-Speed CI Groups, Multi-Layer Caching & Unified `ci-merge-gate` (Priority: P1)

As a maintainer and contributor operating at scale, I want ALOS's fragmented 18-workflow sprawl consolidated into 7 cohesive, multi-layer cached pipelines behind a single terminal `ci-merge-gate` (`pull_request`, `merge_group`, `push`)—reusing `brandon-fox/.github` composite actions and existing `scripts/` runners—so static gates finish in `< 15s` on a single warm VM, untouched language lanes skip cleanly without deadlocking branch protection, external OSS fork PRs never fail on write-token steps, and zero broken, secret-leaking, or vulnerable changes can merge to `main`.

**Why this priority**: Currently 18 separate workflows boot 26+ VMs per PR, syncing `uv` 12+ times (`ruff`, `mypy`, `bandit`, `uv-lock`, `pyadr`, `speckit`, `code-review-bot`, `crewai-validation` all on separate VMs), running `pytest` 3× post-merge, masking `dependency-review` and `gitleaks` with `continue-on-error: true`, and leaving 14+ jobs unrequired on `main`.

**Independent Test**: Validate consolidated 7-workflow topology, action SHA/comment pins, job-level permissions, fork-PR token guards, cache definitions, and `ci-merge-gate` upstream failure/cancellation semantics via `pytest tests/test_github_workflows.py tests/meta/`.

**Acceptance Scenarios**:

1. **Given** any PR, `merge_group`, or `main` push, **When** `Quality Gate` executes, **Then** grouped `python-static` runs `uv lock --check`, `ruff`, `mypy` (with cached `.mypy_cache`), `bandit`, `pyadr`, SpecKit validation, and AST exception-justification checks in a single VM checkout rather than 7 separate VMs, while `code-review-bot.yml`, `spec-analyzer-bot.yml`, and duplicate `crewai-validation` VMs are retired/folded in.
2. **Given** untouched paths (e.g., docs-only PR) vs. workflow/code edits, **When** `dorny/paths-filter` evaluates changes, **Then** `.github/**`, `docs/**`, `specs/**`, and `.specify/**` edits still trigger `pr-governance` (`actionlint` + `zizmor` + SHA pins + SpecKit PR digest + meta-tests) and `container-and-docs` (`mkdocs build --strict` + `lychee`), and `ci-merge-gate` (`if: always()`) passes only when every active job succeeded and every `skipped` job was legitimately path-filtered.
3. **Given** an external contributor PR opened from a fork (`head.repo.full_name != github.repository`), **When** CI executes, **Then** all read-only verification gates run and gate `ci-merge-gate` while write-scoped steps (`actions/labeler`, PR comments) skip cleanly without `403` token failures.

---

### User Story 2 - Zero-Bloat Vetted PR Drafts & Trunk-Based Branch Governance (Priority: P1)

As an OSS maintainer running stacked and autonomous PRs, I want Draft PRs to stay in Draft state while CI runs—validating branch naming prefixes, stack base alignment, Conventional Commit PR titles, PR/Issue templates, auto-labels, SpecKit/ADR references, and SpecKit PR review summaries inside `pr-governance`—promoting `pr.draft` to Ready only after `ci-merge-gate` succeeds on `head.sha` (and requiring `1` approval on non-human / non-maintainer PRs).

**Why this priority**: Fixes the live bug in `auto-merge.yml` where every Draft PR is promoted via `gh pr ready` immediately upon creation before CI or metadata checks pass, without inventing custom Python vetting frameworks.

**Independent Test**: Execute `@mocked` and `@live` BDD scenarios verifying branch-prefix regexes, stacked PR (`base != main` or `wip`/`stacked` label) hold rules, non-human `1`-approval enforcement, fork-PR safety, and `ci-merge-gate`-gated draft promotion.

**Acceptance Scenarios**:

1. **Given** a Draft PR with pending/failing `ci-merge-gate`, a `wip`/`do-not-merge`/`stacked` hold label, `base != main`, an invalid branch prefix, or `alos/`/`crates/` code edits lacking SpecKit/ADR linkage, **When** `pr-governance` and `pr-automation.yml` run, **Then** Draft promotion (`gh pr ready`) is blocked with actionable check annotations.
2. **Given** a Draft PR targeting `main` with valid branch prefix, Conventional title, passing `pr-governance` + `ci-merge-gate` on `head.sha`, and no hold labels, **When** `pr-automation.yml` runs on `workflow_run` completion (eliminating the `check_run` cascade storm), **Then** the PR is marked Ready and queued for squash auto-merge (requiring `1` approval when authored by a non-human / non-maintainer account).

---

### User Story 3 - Declarative `main` & `v*` Tag Protection Governance-as-Code (Priority: P1)

As the repository owner, I want `main` branch protection, `refs/tags/v*` tag immutability, and repository merge/Actions security settings defined in `.github/rulesets/{repo-settings,main-branch,release-tags}.json` and synced/audited by a compact `gh api` script (`scripts/sync_github_governance.py`), including an automatic collaborator-count sentinel alerting when a second human user is added so `required_approving_review_count` is raised to `1`.

**Why this priority**: Replaces stale August-2026 UI click-ops (`Ruleset 20200177`), locks release tags against deletion or force-moves, guarantees `PR_TITLE` squash titles for automated releases, and codifies the single-to-multi-contributor governance transition.

**Independent Test**: Run `scripts/sync_github_governance.py --check` against `@mocked` drifted/clean/multi-collaborator GitHub API payloads and `@live` `brandon-fox/alos` ruleset endpoints.

**Acceptance Scenarios**:

1. **Given** `.github/rulesets/*.json`, **When** `sync_github_governance.py --check` runs in `nightly-health.yml` or locally, **Then** any drift in required status checks (`ci-merge-gate`), `required_signatures`, `required_linear_history`, `required_review_thread_resolution`, `squash_merge_commit_title: "PR_TITLE"`, `sha_pinning_required: true`, `v*` tag protection, or collaborator count (`> 1` human collaborator while `required_approving_review_count == 0`) exits non-zero or opens a governance alert.
2. **Given** initial rollout via `--apply`, **When** `sync_github_governance.py` executes, **Then** it verifies `ci-merge-gate` has reported on `main` HEAD before updating `Ruleset 20200177`, preventing self-deadlock on in-flight PRs.

---

### User Story 4 - Reuse-First Automated Releases (`release-please`), Cached Maturin/GHCR Builds & Nightly Matrix (Priority: P1)

As an OSS user and release maintainer, I want `googleapis/release-please-action` to automate lockstep SemVer bumps (`pyproject.toml`, `Cargo.toml`, `sonar-project.properties`, `CITATION.cff`) and Keep-a-Changelog `CHANGELOG.md` PRs—triggering `PyO3/maturin-action` (`sccache: true`) cross-platform wheels, non-root multi-arch GHCR containers, CycloneDX SBOMs, `SHA256SUMS.txt`, and `actions/attest-build-provenance` SLSA attestations—backed by a consolidated daily `nightly-health.yml` multi-OS × multi-Python build & security sweep.

**Why this priority**: Delivers full enterprise release automation, real compiled `alos_native` wheels, and cryptographic supply-chain provenance using battle-tested upstream actions with zero custom release-script maintenance.

**Independent Test**: Verify `release-please-config.json` + `.release-please-manifest.json` schema/version parity in meta-tests, smoke-test built `maturin` + Python wheels in `--isolated --no-project` venvs, and verify non-root container `HEALTHCHECK` execution.

**Acceptance Scenarios**:

1. **Given** Conventional Commits squash-merged onto `main`, **When** `release-please.yml` runs (via `push` or `workflow_run` fallback when `GITHUB_TOKEN` merges suppress `push`), **Then** `googleapis/release-please-action` opens/updates a `chore(main): release X.Y.Z` PR updating all 4 versioned manifests and `CHANGELOG.md` without erasing history.
2. **Given** a merged `chore(main): release X.Y.Z` PR (or `workflow_dispatch` release cut), **When** `release-please` outputs `release_created == 'true'` and invokes `release-packaging.yml` via `workflow_call`, **Then** cross-OS `maturin` wheels (`linux`, `windows`, `macos`), Python sdist, multi-arch non-root GHCR images, CycloneDX SBOMs, `SHA256SUMS.txt`, and SLSA provenance attestations are built, smoke-tested in clean venvs, and attached to the GitHub Release.
3. **Given** `nightly-health.yml` running on daily/weekly schedules, **When** the 3-OS (`ubuntu`, `windows`, `macos`) × Python (`3.11`–`3.13`) matrix, `maturin` wheel smoke, locked `uv export --frozen` `pip-audit`, `cargo-deny`, benchmarks, and ruleset drift checks run, **Then** any failure opens or updates a single deduplicated health issue per category.

### Edge Cases

- **Fork PR Read-Only `GITHUB_TOKEN`**: Write-permission steps (`labeler`, SpecKit PR digest comment, `dependency-review` comments) check `head.repo.full_name == github.repository` so external OSS contributors never fail CI on token permissions.
- **Upstream-Failure `skipped` Trap in `ci-merge-gate`**: `ci-merge-gate` distinguishes legitimate path-filter skips (`changes.outputs.<lane> == 'false'`) from dependency-failure skips (`combined-coverage` skipped because `pytest-windows` failed), failing hard on the latter.
- **`GITHUB_TOKEN` Push/Tag Suppression**: `pr-automation.yml`, `post-merge-pipeline.yml`, and `release-please.yml` support `workflow_run` / direct `workflow_call` chaining so pipelines fire reliably even when `PR_QUEUE_TOKEN` is unset.
- **Cache Eviction Isolation**: BuildKit GHA caches use distinct `scope=` keys (`alos-runtime`, `alos-sandbox-base`, `alos-sandbox-full`) and Rust uses `Swatinem/rust-cache` (`workspaces: crates/alos_native` + committed `Cargo.lock`) + `maturin` `sccache: true` so jobs share compiler artifacts without cache thrashing.
- **Single-to-Multi-Maintainer Transition**: While `@brandon-fox` is the sole repository collaborator, GitHub prevents self-approval so `main-branch.json` sets `required_approving_review_count: 0`, non-human PRs enforce `1` review approval in `pr-automation.yml`, and `sync_github_governance.py --check` alerts immediately once `collaborators > 1`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001 (Workflow Sprawl Consolidation & Reusable Composite Setup)**: Repository MUST consolidate 18 fragmented workflows into **7 cohesive pipelines** (`quality-gate.yml`, `pr-automation.yml`, `security-compliance.yml`, `release-please.yml`, `release-packaging.yml`, `nightly-health.yml`, `post-merge-pipeline.yml`, retiring 14 redundant files including `code-review-bot.yml` and folding `spec-analyzer-bot.yml` into `pr-governance`), backed by `.github/actions/setup-python-ci/action.yml` wrapping `brandon-fox/.github/setup-uv-cached` + `.mypy_cache`/`.ruff_cache`/`.hypothesis` caching.
- **FR-002 (Multi-Layer Caching at Scale)**: Workflows MUST cache `uv` environments (`setup-uv-cached`), `.mypy_cache` + `.ruff_cache` incremental analysis caches, ML weights (`cache-ml-weights`), Rust crates (`Swatinem/rust-cache` keyed on committed `crates/alos_native/Cargo.lock`), Rust compiler objects (`sccache: true` in `PyO3/maturin-action`), and scope-isolated Docker BuildKit GHA layer caches (`type=gha,scope=<image>`).
- **FR-003 (Unified `ci-merge-gate` & Merge Queue Support)**: `quality-gate.yml` MUST trigger on `pull_request`, `merge_group`, and `push(main)`, expand `dorny/paths-filter` to cover `.github/**`, `docs/**`, `specs/**`, and `.specify/**`, and expose a terminal `ci-merge-gate` (`if: always()`) job enforcing that every active lane succeeded and only untouched path-filtered lanes skipped.
- **FR-004 (Vetted Draft PR Promotion, Non-Human Approval & Branch Strategy Gate)**: `pr-governance` MUST enforce branch prefix conventions (`feat/`, `fix/`, `chore/`, `docs/`, `ci/`, `refactor/`, `test/`, `build/`, `perf/`, `release/`, `hotfix/`, `stack/`, `dependabot/`, `autofix/`, `NNN-*`), Conventional PR titles (`amannn/action-semantic-pull-request`), auto-labeling (`actions/labeler`), SpecKit/ADR traceability + in-place SpecKit PR summary comment, and `First-ADE/ade-axioms`; `pr-automation.yml` MUST replace the `check_run` trigger storm with `workflow_run`, gate `gh pr ready` draft promotion on passing `ci-merge-gate` + `base == 'main'` + absence of `wip`/`do-not-merge`/`stacked` hold labels, and require `1` approval on non-human / non-owner PRs (auto-approving only green `semver-minor`/`semver-patch` Dependabot & `release-please` PRs) while preserving Spec `033` signed rebases.
- **FR-005 (OSS Templates, Docs Strictness & Fork-PR Safety)**: Repository MUST provide `.github/PULL_REQUEST_TEMPLATE.md`, `.github/ISSUE_TEMPLATE/{bug_report.yml,feature_request.yml,config.yml}`, `CONTRIBUTING.md`, updated `SECURITY.md` (`0.1.x`), expanded `.github/labeler.yml`, `mkdocs.yml` (`mkdocs build --strict` + `brandon-fox/.github/links-check.yml` `lychee`), and guard write-token PR steps so fork PRs execute cleanly.
- **FR-006 (Zero Security Theater, Action Static Scanning & Injection Safety)**: Workflows MUST remove `continue-on-error: true` from `dependency-review`, `gitleaks-scan`, and `anchore/sbom-action`, gate `ossf/scorecard-action` on `github.event_name != 'pull_request'`, upgrade `github/codeql-action` to cover `python`, `rust`, and `actions`, run `rhysd/actionlint` + `zizmorcore/zizmor-action` + SHA-to-tag pin checks, and eliminate all `${{ }}` `run:` shell injections in `post-merge-pipeline.yml`.
- **FR-007 (Rust Lockfile, `cargo-deny` & Maturin Wheel Smoke)**: Repository MUST commit `crates/alos_native/Cargo.lock`, add `deny.toml` (`EmbarkStudios/cargo-deny-action` checking advisories, licenses, and bans), add `cargo` + grouped `github-actions` updates in `.github/dependabot.yml` (grouping `uv` dev dependencies consistently), and run `rust-native` across `ubuntu-latest` + `windows-latest` including `clippy --all-targets --no-default-features` and `maturin build` + `--isolated` venv Python import smoke tests.
- **FR-008 (AST Exception Justification & Real Pre-Commit Hooks)**: `tests/meta/test_code_quality_ast.py` MUST enforce inline or preceding justification comments on every `# noqa`, `# type: ignore`, `# pragma: no cover`, and `NOSONAR` token across `alos/` and `tests/`, and `.pre-commit-config.yaml` MUST remove sham `print()` Sonar hooks and enforce `--cov-fail-under=90` on `pre-push`.
- **FR-009 (Hermetic Non-Root Container & `.dockerignore`)**: Repository MUST add `.dockerignore`, harden `Dockerfile` with multi-stage `uv sync --frozen --no-dev` + compiled `alos_native` wheel installation, non-root `alos` user, OCI labels, and `HEALTHCHECK`, and test both `base` and `full` targets of `Dockerfile.sandbox`.
- **FR-010 (Declarative GitHub Rulesets & Collaborator Sentinel)**: Repository MUST store `.github/rulesets/{repo-settings,main-branch,release-tags}.json` and compact `scripts/sync_github_governance.py` (`--check` / `--apply`) enforcing `required_signatures`, `required_linear_history`, `required_review_thread_resolution: true`, `dismiss_stale_reviews_on_push: true`, `require_extra_approval_for_unattributed_changes: true`, `squash_merge_commit_title: "PR_TITLE"`, `allow_rebase_merge: false`, `sha_pinning_required: true`, `minimum_coverage: 90`, `ci-merge-gate`, immutable signed `refs/tags/v*` protection, and a collaborator-count check alerting when `> 1` human collaborator exists so `required_approving_review_count` is raised to `1`.
- **FR-011 (Release Please Lockstep SemVer Cuts & SLSA Provenance)**: Repository MUST configure `googleapis/release-please-action` via `release-please-config.json` + `.release-please-manifest.json` (`extra-files` syncing `pyproject.toml`, `crates/alos_native/Cargo.toml`, `sonar-project.properties`, `CITATION.cff`, and additive `CHANGELOG.md`; retiring `post-merge-pipeline.yml`'s destructive `generate-changelog` job), chaining via `workflow_call` into `release-packaging.yml` to publish cross-OS `PyO3/maturin-action` wheels, sdist, multi-arch GHCR images, CycloneDX SBOMs, `SHA256SUMS.txt`, and `actions/attest-build-provenance` SLSA attestations.
- **FR-012 (Consolidated Nightly Multi-OS Build, Benchmark & Drift Sweep)**: `nightly-health.yml` MUST run `ubuntu-latest`, `windows-latest`, and `macos-latest` × Python `3.11`–`3.13` tests + native wheel install smoke, locked `uv export --frozen` `pip-audit`, compiled native benchmarks (without `|| true`), `sync_github_governance.py --check`, `Main Guardian` push/schedule workflow health (fixing literal `\\n` rendering), and `actions/stale` with aligned `wip`/`do-not-merge`/`stacked`/`automated` exemptions.
- **FR-013 (Mocked + Live BDD & Meta-Test Verification)**: All consolidated workflow invariants, lockstep manifest parity, ruleset/collaborator drift checks, and Draft PR promotion gates MUST be verified via `tests/test_github_workflows.py`, `pytest-bdd` (`tests/features/13_enterprise_cicd_governance.feature`), and `behave` (`features/enterprise_cicd_pipeline.feature`) covering both `@mocked` and `@live` scenarios.

### Key Entities

- **Consolidated 7-Workflow Suite (`quality-gate.yml`, `pr-automation.yml`, `security-compliance.yml`, `release-please.yml`, `release-packaging.yml`, `nightly-health.yml`, `post-merge-pipeline.yml`)**: Zero-overlap pipeline topology replacing 18 fragmented workflows.
- **`.github/actions/setup-python-ci/action.yml`**: Reusable composite setup action layering `.mypy_cache`, `.ruff_cache`, and `.hypothesis` caches onto `brandon-fox/.github/setup-uv-cached`.
- **`.github/rulesets/{repo-settings,main-branch,release-tags}.json`**: Declarative source of truth for GitHub repository merge policy, `main` branch protection, and `v*` tag immutability.
- **`release-please-config.json` & `.release-please-manifest.json`**: Declarative lockstep SemVer and Keep-a-Changelog configuration driving `googleapis/release-please-action`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001 (Speed & Consolidation)**: Total workflow file count drops from 18 to **7**, per-PR VM spawns drop by `>= 50%` (consolidating 8 Python/governance/bot VMs into 2 cached jobs), and warm static checks execute in `< 20s`.
- **SC-002 (Zero-Bypass Main & Draft Protection)**: `0` unvetted Draft PRs promote before `ci-merge-gate` passes, `1` approval is enforced on non-human PRs, `0` security steps use `continue-on-error: true` or `|| true`, `100%` of fork PRs run without write-token failures, and `sync_github_governance.py --check` reports `0` ruleset drift against live `brandon-fox/alos`.
- **SC-003 (Enterprise Release & Supply Chain)**: `release-please` maintains lockstep versions across all 4 manifests + `CHANGELOG.md`, and `release-packaging.yml` produces clean-venv-verified cross-OS `maturin` wheels, non-root GHCR images, `SHA256SUMS.txt`, CycloneDX SBOMs, and verifiable SLSA OIDC provenance attestations (`v0.1.0` inaugural release).
- **SC-004 (DRY Zero-Bloat Footprint)**: Zero bespoke CI framework packages are added under `alos/`, every PR slice stays within `200–360` non-lockfile LOC (`<= 1,000` hard gate), and `>= 90%` dual-OS branch + `@mocked`/`@live` BDD coverage passes cleanly.

## Assumptions

- `brandon-fox/.github` composite/reusable actions (`setup-uv-cached`, `setup-rust-cached`, `cache-ml-weights`, `pr-size-guard.yml`, `links-check.yml`, `ci-autofix.yml`) and `First-ADE/ade-axioms` remain the shared upstream primitives, pinned by 40-character commit SHA.
- While `@brandon-fox` is the sole contributor, `main-branch.json` sets `required_approving_review_count: 0` (since GitHub prohibits self-approval) while `pr-automation.yml` enforces `1` approval on non-human PRs and `sync_github_governance.py --check` triggers an alert to raise `required_approving_review_count: 1` as soon as a second human collaborator is added.
