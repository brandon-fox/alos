# Specification Quality & Compliance Checklist: Enterprise-Grade DRY Open-Source CI/CD Pipeline (`038`)

**Purpose**: Validate SpecKit completeness, DRY reuse-over-rebuild discipline, caching/speed architecture, and acceptance criteria
**Created**: 2026-11-24
**Feature**: [spec.md](../spec.md) | [plan.md](../plan.md) | [tasks.md](../tasks.md)

## Reuse, Consolidation & Architecture Governance

- [x] Zero bespoke CI packages added under `alos/`; reuses `release-please`, `maturin-action`, `cargo-deny`, `attest-build-provenance`, `sbom-action`, `actionlint`, `zizmor`, `labeler`, `semantic-pull-request`, and `brandon-fox/.github` actions
- [x] Consolidates 18 fragmented workflows into **7** cohesive grouped pipelines behind terminal `ci-merge-gate` (`pull_request`, `merge_group`, `push`)
- [x] Multi-layer caching specified (`uv`, `.mypy_cache`/`.ruff_cache`/`.hypothesis`, `Swatinem/rust-cache` + `Cargo.lock`, `maturin` `sccache`, scope-isolated BuildKit GHA caches)
- [x] Architectural decisions recorded via `pyadr` in [ADR-0026](../../../docs/adr/0026-consolidate-ci-workflows-into-cached-groups-behind-unified-merge-gate-and-declarative-rulesets.md) and [ADR-0027](../../../docs/adr/0027-adopt-release-please-maturin-sccache-and-github-oidc-slsa-provenance-over-custom-release-scripts.md)
- [x] Delivery decomposed into 5 surgical `200–360` LOC PR slices respecting `PR Size Guard (<= 1,000 lines)`

## Functional & Edge-Case Acceptance Gates

- [ ] **FR-001 / FR-002 / FR-003**: `setup-python-ci` composite action active; static checks grouped on 1 warm VM (`< 20s`); `ci-merge-gate` distinguishes path-filtered skips from upstream-failure skips; fork PRs skip write-token steps cleanly
- [ ] **FR-004 / FR-005**: Branch naming, Conventional PR titles, SpecKit PR digest, PR/Issue templates, `CONTRIBUTING.md`, `SECURITY.md`, `mkdocs build --strict`, and `lychee` enforced; Draft PRs stay Draft until `ci-merge-gate` passes on `head.sha`; non-human PRs require `1` approval
- [ ] **FR-006 / FR-007**: Zero `continue-on-error: true` or `|| true` security masks; zero `${{ }}` `run:` shell injections; `actionlint` + `zizmor` + CodeQL (`python`, `rust`, `actions`) + `Cargo.lock` + `cargo-deny` + dual-OS `maturin` wheel import smoke passing
- [ ] **FR-008 / FR-009**: AST exception-justification check in `tests/meta/test_code_quality_ast.py`; sham Sonar `print()` hooks removed from `.pre-commit-config.yaml` (`--cov-fail-under=90`); `.dockerignore` + non-root `Dockerfile` + `Dockerfile.sandbox` (`base` + `full`) verified
- [ ] **FR-010 / FR-011 / FR-012 / FR-013**: `.github/rulesets/*.json` + `sync_github_governance.py --check` (`0` drift on `main` & `v*` tags + `> 1` collaborator sentinel); `release-please` lockstep manifests + `maturin` wheels + GHCR + CycloneDX SBOM + `SHA256SUMS.txt` + SLSA provenance; daily `nightly-health.yml`; `@mocked` + `@live` BDD passing (`>= 90%` coverage)
