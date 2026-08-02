# Feature Specification: GitHub Actions Workflow Expansion

**Feature Branch**: `026-github-actions-expansion`
**Created**: 2026-08-02
**Status**: Approved

---

## User Scenarios & Testing

### User Story 1 - Security & Vulnerability Auditing (Priority: P1)

As a security-conscious developer, I want continuous automated scanning for leaked secrets, OpenSSF security scorecard analysis, and CodeQL SAST code scanning so that vulnerabilities are detected immediately.

**Why this priority**: Preventing security vulnerabilities and credential leaks before code enters production is critical.

**Independent Test**: Push commits with simulated patterns or triggers to verify `security-compliance.yml` executes Gitleaks, Scorecard, and CodeQL.

**Acceptance Scenarios**:
1. **Given** a pull request or main branch push, **When** `security-compliance.yml` triggers, **Then** `gitleaks-scan` scans for token leaks.
2. **Given** a scheduled or main branch trigger, **When** CodeQL runs, **Then** Python and Rust SAST security queries execute without error.

---

### User Story 2 - Automated Release & Packaging Validation (Priority: P1)

As a maintainer, I want automated workflows to build Python wheels, compile Rust native release binaries, validate Docker multi-arch container images, and generate Software Bill of Materials (SBOM) when releasing or testing code.

**Why this priority**: Eliminates manual packaging steps and guarantees release artifact integrity.

**Independent Test**: Trigger `release-packaging.yml` manually or via push tag `v*` to verify `uv build`, Rust compilation, Docker buildx dry-run, and SBOM generation.

---

### User Story 3 - SpecKit & Architecture Governance (Priority: P2)

As an ALOS core architect, I want automated SpecKit matrix validation and ADR provenance checks to ensure specs are complete and decision records remain uncorrupted.

**Why this priority**: Enforces repository architectural standards automatically in CI.

---

### User Story 4 - Performance Benchmark & Regression Prevention (Priority: P2)

As a performance engineer, I want performance benchmark workflows that execute Rust micro-benchmarks and Python latency suites to flag regressions early.

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST provide a `security-compliance.yml` workflow executing Gitleaks secret detection (`gitleaks/gitleaks-action@v2`).
- **FR-002**: System MUST provide OpenSSF Scorecard assessment (`ossf/scorecard-action@v2.4.0`) in `security-compliance.yml`.
- **FR-003**: System MUST execute GitHub CodeQL static security analysis for Python and Rust in `security-compliance.yml`.
- **FR-004**: System MUST provide a `release-packaging.yml` workflow building Python wheel artifacts with `uv build` and `twine check`.
- **FR-005**: System MUST validate Rust native release compilation (`cargo build --release`) in `release-packaging.yml`.
- **FR-006**: System MUST perform Docker multi-architecture container validation and CycloneDX/SPDX SBOM generation in `release-packaging.yml`.
- **FR-007**: System MUST provide automated release notes drafting on `v*` tag triggers.
- **FR-008**: System MUST provide a `speckit-governance.yml` workflow auditing all `specs/` directories for spec completeness (`spec.md`, `plan.md`, `tasks.md`, `checklists/requirements.md`).
- **FR-009**: System MUST check ADR repository integrity (`uv run pyadr check-adr-repo`) in `speckit-governance.yml`.
- **FR-010**: System MUST provide a `performance-benchmark.yml` workflow running Rust `cargo bench` and Python performance test suites.
- **FR-011**: System MUST enhance `quality-gate.yml` with `uv lock --check` and dependency license compliance checks.
- **FR-012**: System MUST enhance `rust-ci.yml` with `cargo fmt --check` and dependency security audit checks.

## Success Criteria

- **SC-001**: 100% of workflow YAML files pass schema and syntax validation via pytest meta-test `tests/test_github_workflows.py`.
- **SC-002**: All 4 new workflow groups execute cleanly without invalid keys or broken action references.
