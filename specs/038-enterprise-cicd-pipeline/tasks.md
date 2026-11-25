# Tasks: Enterprise-Grade DRY Open-Source CI/CD, Vetted PR Drafts, Main Protection & Automated Release Pipeline

**Input**: `/specs/038-enterprise-cicd-pipeline/` (`spec.md`, `plan.md`, `checklists/requirements.md`) and `docs/adr/0026*.md`..`0027*.md`

**Prerequisites**: `plan.md` (required), `spec.md` (required), `checklists/requirements.md`

**DRY & Speed Mandate**: Reuse upstream SHA-pinned actions (`release-please`, `maturin-action`, `cargo-deny`, `attest-build-provenance`, `actionlint`, `zizmor`, `brandon-fox/.github`) instead of custom Python frameworks. Every PR (`200–360` non-lockfile LOC) follows Red-Green-Refactor TDD with unit, meta, `pytest-bdd`, and `@mocked`/`@live` `behave` coverage (`>= 90%` branch floor).

## Phase 1: Specification & Reuse-First Architecture Decisions (`PR-01`)

- [x] T001 Initialize and author DRY `specs/038-enterprise-cicd-pipeline/` (`spec.md`, `plan.md`, `tasks.md`, `checklists/requirements.md`) (`PR-01`)
- [x] T002 Propose, author, and accept `ADR-0026` (consolidated cached workflow groups, unified `ci-merge-gate`, declarative rulesets, non-human approval + collaborator sentinel) and `ADR-0027` (`release-please`, `maturin` `sccache`, OIDC SLSA provenance) via `pyadr` (`PR-01`)

---

## Phase 2: Local Quality Gates, Rust `Cargo.lock`/`cargo-deny`, Docs & Non-Root Container (`PR-02`, Priority: P1)

**Goal (`[US1]` & `[US4]`)**: Lock down local pre-commit/pre-push hooks, AST suppression justifications, `mkdocs build --strict`, reproducible Rust `Cargo.lock` + `deny.toml`, `.dockerignore`, and non-root `Dockerfile` before rewiring GitHub workflows.

- [x] T003 [P] [US1] Add failing RED meta-tests in `tests/meta/test_code_quality_ast.py` (enforcing inline/preceding justification comments on `# noqa`, `# type: ignore`, `# pragma: no cover`, `NOSONAR`) and `tests/test_packaging_and_docs_manifests.py` (verifying `Cargo.lock`, `deny.toml`, `mkdocs.yml`, `.dockerignore`, non-root `Dockerfile`, and `cargo` Dependabot config) (`PR-02`)
- [x] T004 [US1] Remediate any unjustified inline suppressions, update `.pre-commit-config.yaml` (remove sham `print()` Sonar hooks, enforce `--cov-fail-under=90` on `pre-push`), and add `mkdocs.yml` + `mkdocs` dev dependency (`PR-02`)
- [x] T005 [P] [US4] Generate `crates/alos_native/Cargo.lock`, author `deny.toml`, update `.github/dependabot.yml` (`cargo` + grouped `github-actions` & `uv` dev groups), and add `.dockerignore` + hardened multi-stage non-root `Dockerfile` (`PR-02`)

---

## Phase 3: Consolidated Cached CI Groups, `ci-merge-gate`, Vetted Draft PRs & OSS Templates (`PR-03`, Priority: P1) 🎯

**Goal (`[US1]` & `[US2]`)**: Collapse 18 fragmented workflows into 7 grouped, cached pipelines behind `ci-merge-gate` (`pull_request`, `merge_group`, `push`), fix premature Draft PR promotion, enforce `1` approval on non-human PRs, harden security scans, and add OSS contributor/issue/PR templates with fork-PR safety.

- [ ] T006 [P] [US1] Rewrite `tests/test_github_workflows.py` and `tests/features/13_enterprise_cicd_governance.feature` (`# spec: 038-enterprise-cicd-pipeline`) + `tests/step_defs/test_13_enterprise_cicd_governance.py` with RED assertions for consolidated 7-workflow layout, `ci-merge-gate` upstream-failure/skip semantics, `merge_group`, fork-PR guards, cache scopes, zero `continue-on-error` on security steps, and zero `${{ }}` `run:` injections (`PR-03`)
- [ ] T007 [US1] Create `.github/actions/setup-python-ci/action.yml` (wrapping `brandon-fox/.github/setup-uv-cached` + `.mypy_cache`/`.ruff_cache`/`.hypothesis` caching) and upgrade `.github/workflows/quality-gate.yml` (`pr-governance` w/ SpecKit digest, `changes`, 1-VM `python-static`, dual-OS `pytest`, dual-OS `rust-native` with `cargo-deny` + `maturin` wheel smoke, `container-and-docs` with `sandbox` `base`+`full` + `trivy` + `mkdocs --strict` + `lychee`, `dependency-review`, and terminal `ci-merge-gate`) (`PR-03`)
- [ ] T008 [US2] Create `.github/workflows/pr-automation.yml` (merging `auto-merge.yml` + `autofix.yml`, gating `gh pr ready` on `workflow_run` `Quality Gate` success + `base == 'main'` + no `wip`/`do-not-merge`/`stacked` labels, requiring `1` approval on non-human PRs, preserving Spec `033` `signed_pr_rebase.py`), harden `security-compliance.yml` (`gitleaks` strict, CodeQL `python`+`rust`+`actions`, non-PR Scorecard) and `post-merge-pipeline.yml` (1 coverage run, `workflow_run` fallback, injection fixes, `.github/scripts/{complexity_scanner,spec_gap_analyzer}.py` exit/stdout fixes), and delete 10 superseded workflow files (`PR-03`)
- [ ] T009 [P] [US2] Add `.github/PULL_REQUEST_TEMPLATE.md`, `.github/ISSUE_TEMPLATE/{bug_report.yml,feature_request.yml,config.yml}`, `CONTRIBUTING.md`, update `SECURITY.md` (`0.1.x`), and expand `.github/labeler.yml` (`PR-03`)

---

## Phase 4: `release-please` SemVer Automation, Cached Maturin/GHCR/SLSA Packaging & Nightly Matrix (`PR-04`, Priority: P1)

**Goal (`[US4]`)**: Configure zero-custom-code lockstep SemVer release PRs and tag cuts via `googleapis/release-please-action`, cross-platform `maturin` (`sccache`) wheels + multi-arch GHCR + CycloneDX SBOM + SLSA provenance, and consolidated `nightly-health.yml`.

- [ ] T010 [P] [US4] Add RED meta-tests in `tests/test_github_workflows.py` verifying lockstep version parity across `pyproject.toml`, `crates/alos_native/Cargo.toml`, `sonar-project.properties`, `CITATION.cff`, and `.release-please-manifest.json`, plus `release-please` -> `release-packaging` `workflow_call` chaining and SLSA attestation permissions (`PR-04`)
- [ ] T011 [US4] Add `release-please-config.json`, `.release-please-manifest.json` (`0.1.0`), `.github/release.yml`, and `.github/workflows/release-please.yml` (`push` + `workflow_run` + `workflow_dispatch`), retiring `generate-changelog` from `post-merge-pipeline.yml` (`PR-04`)
- [ ] T012 [US4] Upgrade `.github/workflows/release-packaging.yml` (`workflow_call` + `v*` tags: `PyO3/maturin-action` with `sccache: true` across Linux/Windows/macOS, `uv build --sdist`, `--isolated` venv CLI smoke test, multi-arch GHCR push, CycloneDX SBOM, `SHA256SUMS.txt`, `actions/attest-build-provenance`, GitHub Release upload) and create consolidated `.github/workflows/nightly-health.yml` (retiring the 4 remaining legacy `scheduled-*.yml` + `main-guardian.yml` + `performance-benchmark.yml` files -> exactly 7 workflows!) (`PR-04`)

---

## Phase 5: Declarative GitHub Rulesets, `@mocked`+`@live` Behave Suite & Zero-Downtime Live Cutover (`PR-05`, Priority: P1)

**Goal (`[US3]`)**: Codify `main` branch and `v*` tag protection in `.github/rulesets/*.json`, wire `sync_github_governance.py` (with `> 1` collaborator sentinel) into `nightly-health.yml`, run full `@mocked` + `@live` `behave` verification, apply live rulesets onto `brandon-fox/alos`, and verify `v0.1.0` release readiness.

- [ ] T013 [P] [US3] Write failing `@mocked` and `@live` `behave` scenarios in `features/enterprise_cicd_pipeline.feature` and `features/steps/enterprise_cicd_steps.py` plus unit tests in `tests/test_sync_github_governance.py` (`PR-05`)
- [ ] T014 [US3] Author `.github/rulesets/{repo-settings,main-branch,release-tags}.json` and implement compact `scripts/sync_github_governance.py` (`--check` / `--apply` with pre-flight `ci-merge-gate` check-run verification and `> 1` human collaborator sentinel) wired into `nightly-health.yml` (`PR-05`)
- [ ] T015 [US3] Update `GIT_WORKFLOW.md` and `scripts/traceability.py` -> `docs/traceability.md`, merge `PR-05` to `main`, execute `sync_github_governance.py --apply` on `brandon-fox/alos`, confirm `0` live ruleset drift, and trigger/verify inaugural `v0.1.0` release (`PR-05`)

---

## Dependencies & Execution Flow

- **`PR-01` (SpecKit `038` + ADRs `0026`–`0027`)** -> **`PR-02` (Local hooks, `Cargo.lock`/`deny.toml`, `mkdocs`, `.dockerignore`, non-root `Dockerfile`)** -> **`PR-03` (Consolidated cached `quality-gate.yml` + `ci-merge-gate` + `pr-automation.yml` + OSS templates)** -> **`PR-04` (`release-please` + `maturin`/`sccache`/GHCR/SLSA + `nightly-health.yml`)** -> **`PR-05` (Declarative `.github/rulesets/*.json` + collaborator sentinel + `@mocked`/`@live` Behave + live ruleset cutover)**.
