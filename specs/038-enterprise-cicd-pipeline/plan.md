# Implementation Plan: Enterprise-Grade DRY Open-Source CI/CD, Vetted PR Drafts, Main Protection & Automated Release Pipeline

**Branch**: `enterprise_grade_cicd_pipeline` (`038-enterprise-cicd-pipeline`) | **Date**: 2026-11-24 | **Spec**: [spec.md](./spec.md)

**Input**: `specs/038-enterprise-cicd-pipeline/spec.md` and ADRs [0026](../../docs/adr/0026-consolidate-ci-workflows-into-cached-groups-behind-unified-merge-gate-and-declarative-rulesets.md)–[0027](../../docs/adr/0027-adopt-release-please-maturin-sccache-and-github-oidc-slsa-provenance-over-custom-release-scripts.md).

## Summary

Deliver an A+ production-grade open-source CI/CD, branch protection, and release pipeline strictly guided by **Reuse over Rebuild**, **Workflow Group Consolidation**, and **Multi-Layer Caching for Speed at Scale**:
- **Zero Custom Framework Bloat**: Keeps `alos/` 100% pure product code—reusing `googleapis/release-please-action`, `PyO3/maturin-action` (`sccache`), `EmbarkStudios/cargo-deny-action`, `actions/attest-build-provenance`, `anchore/sbom-action`, `rhysd/actionlint`, `zizmorcore/zizmor-action`, `amannn/action-semantic-pull-request`, `actions/labeler`, `brandon-fox/.github` (`setup-uv-cached`, `setup-rust-cached`, `cache-ml-weights`, `pr-size-guard.yml`, `links-check.yml`, `ci-autofix.yml`), `First-ADE/ade-axioms`, and existing `scripts/` / `tests/meta/`.
- **18 Sprawl Workflows -> 7 Grouped, Cached Pipelines**: Eliminates >50% of per-PR VM boot overhead by grouping all Python/governance static gates (`uv lock`, `ruff`, `mypy`, `bandit`, `pyadr`, SpecKit, AST exception docs) into **1 warm cached VM** (`< 15s`) and all PR metadata/axiom/SpecKit-digest/workflow-lint checks into **1 fast `pr-governance` job** (`< 10s`), retiring 14 redundant workflow files behind a single terminal **`ci-merge-gate`**.
- **5 Surgical `200–360` LOC PR Slices**: Respects `PR Size Guard (<= 1,000 lines)`, SSH commit signing, fork-PR token safety, non-human `1`-approval enforcement, collaborator-count sentinel, `merge_group` support, and `@mocked` + `@live` BDD verification.

## Technical Context

**Language/Version**: Python `>=3.11,<3.14` (`3.11`–`3.13` across `ubuntu`, `windows`, `macos`) + Rust 2021 (`crates/alos_native` PyO3 `maturin`)
**Reused Ecosystem & Shared Actions**: `brandon-fox/.github` (`setup-uv-cached`, `setup-rust-cached`, `cache-ml-weights`, `pr-size-guard.yml`, `links-check.yml`, `ci-autofix.yml`), `First-ADE/ade-axioms`, `googleapis/release-please-action`, `PyO3/maturin-action`, `EmbarkStudios/cargo-deny-action`, `actions/attest-build-provenance`, `anchore/sbom-action`, `rhysd/actionlint`, `zizmorcore/zizmor-action`, `amannn/action-semantic-pull-request`, `actions/labeler`, `dorny/paths-filter` (all 40-char SHA-pinned)
**Multi-Layer Caching**: `uv` wheel/env cache + `.mypy_cache`/`.ruff_cache`/`.hypothesis` (`setup-python-ci` composite action) + `Swatinem/rust-cache` (`Cargo.lock`) + `maturin` `sccache: true` + scope-isolated BuildKit GHA caches (`type=gha,scope=alos-{runtime,sandbox-base,sandbox-full}`) + HuggingFace/Torch cache
**Storage / Config**: Declarative JSON/TOML/YAML manifests (`.github/rulesets/*.json`, `release-please-config.json`, `.release-please-manifest.json`, `deny.toml`, `mkdocs.yml`)
**Testing**: `pytest` (`tests/test_github_workflows.py`, `tests/meta/`), `pytest-bdd` (`tests/features/13_enterprise_cicd_governance.feature`), `behave` (`features/enterprise_cicd_pipeline.feature` `@mocked` + `@live`)
**Performance Goals**: `< 10s` `pr-governance`; `< 15s` warm `python-static` (1 VM instead of 8); `< 20s` warm Rust + `cargo-deny`; zero `check_run` cascade storms
**Constraints**: Zero new `alos/*` CI subpackages; `200–360` non-lockfile LOC/PR (`<= 1,000` hard gate); fork-PR read-only token compatibility; 100% 40-char SHA pins with verified version comments; SSH-signed commits; `>= 90%` dual-OS coverage
**Scale/Scope**: 2 ADRs (`0026`–`0027`), 1 local composite cache action, 1 compact ruleset sync CLI (`~95` LOC), 7 consolidated workflows (retiring 14 redundant workflow files), 5 incremental PRs

## Constitution Check

- **I. Determinism & Verification Before Action**: PASS — `ci-merge-gate` deterministically gates Draft promotion and `main` merges; `sync_github_governance.py` validates ruleset schemas and check-run presence before mutating GitHub rulesets.
- **II. Local-First Privacy & Data Sovereignty**: PASS — Static gates, AST exception checks, `cargo-deny`, `mkdocs --strict`, and `--check` ruleset validation run locally offline with zero third-party telemetry.
- **III. Decision Provenance & Audit Integrity**: PASS — Recorded in `ADR-0026` and `ADR-0027`; releases carry `SHA256SUMS.txt`, CycloneDX SBOMs, and GitHub OIDC SLSA build provenance attestations.
- **IV. Test-First Development**: PASS — Each of the 5 PR slices starts with failing RED meta-tests and `@mocked`/`@live` BDD scenarios.
- **V. Safety Matrix Enforcement**: PASS — Fork PRs run strictly read-only (`LOW`); Draft promotion, non-human `1`-approval gating, & `release-please` PRs (`MEDIUM`) gate on `ci-merge-gate`; `main` & `v*` tag rulesets (`HIGH`) enforce cryptographic signatures and zero bypass actors.
- **VI. Human-Centric Non-Intrusiveness**: PASS — Eliminates `check_run` cascades, retires duplicate `code-review-bot.yml` and `chore/bot-changelog` PR spam, folds `spec-analyzer-bot.yml` into `pr-governance`, and deduplicates scheduled health issues.
- **VII. Code Quality, Exception Documentation & Fix-First**: PASS — Enforces justified suppressions via AST in `tests/meta/test_code_quality_ast.py`, replaces sham `print()` Sonar hooks in `.pre-commit-config.yaml`, and removes all `continue-on-error: true` security masks.

## Project Structure (DRY Consolidated Layout)

### Documentation (this feature)

```text
specs/038-enterprise-cicd-pipeline/
├── spec.md                      # FR-001..FR-013, edge cases, measurable outcomes
├── plan.md                      # Reuse-first consolidation, caching matrix & 5-PR roadmap
├── tasks.md                     # Atomic TDD/BDD tasks mapped to 5 PR slices
└── checklists/
    └── requirements.md          # Compliance & verification checklist
```

### Consolidated Repository CI/CD & Governance Topology

```text
.github/
├── actions/
│   ├── setup-git-signing/action.yml          # Existing SSH signing composite action (Spec 033)
│   └── setup-python-ci/action.yml            # NEW: Thin composite wrapping setup-uv-cached + .mypy_cache/.ruff_cache/.hypothesis
├── workflows/                                # CONSOLIDATED: 18 files -> 7 zero-overlap workflows
│   ├── quality-gate.yml                      # Unified PR / merge_group / main gate:
│   │                                         #   pr-governance (size+title+branch+labeler+SpecKit digest+axioms+actionlint+zizmor+pins)
│   │                                         #   changes -> python-static (1 VM!) | pytest-{linux,windows}+combined-cov+fanout
│   │                                         #   | rust-native (linux+win+cargo-deny+maturin smoke)
│   │                                         #   | container-and-docs (Dockerfile+sandbox base/full+trivy+mkdocs+lychee)
│   │                                         #   | dependency-review -> terminal ci-merge-gate (if: always())
│   ├── pr-automation.yml                     # Consolidated auto-merge + autofix + signed_pr_rebase (workflow_run Draft gate + non-human 1-approval)
│   ├── security-compliance.yml               # Strict gitleaks, CodeQL v4 (python, rust, actions), push/cron OpenSSF Scorecard
│   ├── release-please.yml                    # googleapis/release-please-action -> calls release-packaging.yml on release_created
│   ├── release-packaging.yml                 # Reusable/tag pipeline: PyO3/maturin-action (sccache) + GHCR + SBOM + SHA256 + SLSA
│   ├── nightly-health.yml                    # Consolidated daily/weekly: 3-OS x 3-Py matrix + pip-audit + benches + Guardian/Drift + stale
│   └── post-merge-pipeline.yml               # Single-coverage-run Sonar + AST/debt analytics (push + workflow_run fallback)
├── rulesets/
│   ├── repo-settings.json                    # Squash PR_TITLE, sha_pinning_required: true, read-only default token
│   ├── main-branch.json                      # Signatures, linear history, thread resolution, 90% cov, ci-merge-gate
│   └── release-tags.json                     # Immutable signed refs/tags/v* tag protection
├── ISSUE_TEMPLATE/{bug_report.yml,feature_request.yml,config.yml}
├── PULL_REQUEST_TEMPLATE.md
├── release.yml
├── dependabot.yml                            # uv (grouped runtime+dev) + cargo + docker + grouped github-actions
└── labeler.yml                               # Expanded path globs (rust, security, governance, release)

release-please-config.json                    # Lockstep extra-files (pyproject.toml, Cargo.toml, sonar, CITATION.cff)
.release-please-manifest.json                 # Canonical SemVer state ("0.1.0")
deny.toml                                     # Rust cargo-deny advisories, licenses (MIT/Apache/BSD/ISC/MPL), & bans
mkdocs.yml                                    # Strict docs build config (mkdocs build --strict)
CONTRIBUTING.md                               # Contributor, branch naming, stacked PR, & SSH-signing guide
.dockerignore                                 # Excludes .git, .venv, caches, tests, scratch from Docker context
scripts/sync_github_governance.py             # Compact (~95 LOC) gh api ruleset --check / --apply + >1 collaborator sentinel
```

**Retired Sprawl Files (14 Deleted -> 7 Total Workflows)**: `ade-axioms.yml`, `auto-merge.yml`, `autofix.yml`, `code-review-bot.yml`, `main-guardian.yml`, `performance-benchmark.yml`, `pr-title-lint.yml`, `rust-ci.yml`, `sandbox-ci.yml`, `scheduled-dependency-health.yml`, `scheduled-matrix-test.yml`, `scheduled-stale-cleanup.yml`, `spec-analyzer-bot.yml`, `speckit-governance.yml` *(all folded cleanly into the 7 grouped workflows above, with SpecKit PR summary folded into `pr-governance`)*.

## Caching & Concurrency Matrix for Speed at Scale

| Layer | Mechanism | Key / Scope | Speed Impact |
| :--- | :--- | :--- | :--- |
| **Python Env & Wheels** | `brandon-fox/.github/setup-uv-cached` | `uv.lock` | `< 3s` env restore |
| **Incremental MyPy / Ruff / Hypothesis** | `.github/actions/setup-python-ci` (`actions/cache`) | `${{ runner.os }}-py-analysis-${{ hashFiles('pyproject.toml','uv.lock') }}-${{ github.sha }}` | Warm `mypy` `< 1.5s`; 8 jobs -> 2 VMs |
| **Rust Dependencies & Native Wheels** | `Swatinem/rust-cache` + `PyO3/maturin-action` (`sccache: true`) | `crates/alos_native/Cargo.lock` | `< 15s` warm clippy/test/wheel |
| **Docker BuildKit Layers** | `docker/build-push-action` GHA cache | `scope=alos-runtime`, `alos-sandbox-base`, `alos-sandbox-full` | Zero cross-image cache eviction |
| **Concurrency Cancellation** | Per-workflow `concurrency:` groups | `cancel-in-progress: ${{ github.event_name == 'pull_request' }}` | Instant stale PR abort; protects `main`, `merge_group`, & `v*` releases |

## 5-PR Surgical Delivery Roadmap (`200–360` LOC / PR)

| PR | Branch | Est. LOC | Scope & Verification |
| :--- | :--- | :--- | :--- |
| **PR-01** | `docs/038-cicd-spec-and-adrs` | ~360 | `specs/038-enterprise-cicd-pipeline/*`, `.specify/feature.json`, MADR `ADR-0026` & `ADR-0027`, `docs/adr/index.md` |
| **PR-02** | `chore/038-precommit-docs-rust-docker` | ~310 | AST exception-justification check in `tests/meta/test_code_quality_ast.py`, `.pre-commit-config.yaml` real gates (`--cov-fail-under=90`), `mkdocs.yml`, `crates/alos_native/Cargo.lock`, `deny.toml`, `.dockerignore`, hardened non-root `Dockerfile`, `dependabot.yml` (`cargo` + grouped actions/dev) + container/lockfile meta-tests |
| **PR-03** | `ci/038-consolidated-merge-gate-and-vetting` | ~360 | `.github/actions/setup-python-ci/action.yml`, consolidated `quality-gate.yml` (`pr-governance` w/ SpecKit digest + `python-static` + dual-OS `pytest` + `rust-native` + `container-and-docs` + `dependency-review` + `ci-merge-gate` + `merge_group` + fork guards), `pr-automation.yml` (vetted Draft `gh pr ready` + non-human `1`-approval gate), hardened `security-compliance.yml` & `post-merge-pipeline.yml`, retire 10 redundant workflow files, add OSS PR/Issue templates + `CONTRIBUTING.md` + `SECURITY.md` + `labeler.yml` + updated `tests/test_github_workflows.py` |
| **PR-04** | `ci/038-release-please-maturin-and-nightly` | ~320 | `release-please-config.json` + `.release-please-manifest.json` + `.github/release.yml` + `release-please.yml` + upgraded `release-packaging.yml` (`PyO3/maturin-action` `sccache`, `--isolated` smoke, multi-arch GHCR, CycloneDX SBOM, `SHA256SUMS.txt`, `actions/attest-build-provenance` SLSA) + consolidated `nightly-health.yml` (deleting last 4 legacy cron/benchmark files) + `pytest-bdd` scenarios |
| **PR-05** | `feat/038-declarative-rulesets-and-cutover` | ~290 | `.github/rulesets/{repo-settings,main-branch,release-tags}.json`, `scripts/sync_github_governance.py` (`> 1` collaborator sentinel), `@mocked` + `@live` `behave` suite (`features/enterprise_cicd_pipeline.feature`), `GIT_WORKFLOW.md` + `docs/traceability.md`, zero-downtime `--apply` onto `brandon-fox/alos`, and inaugural `v0.1.0` release verification |
