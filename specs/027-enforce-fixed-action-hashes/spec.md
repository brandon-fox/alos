# Feature Specification: Enforce Fixed Action Hashes

**Feature Branch**: `027-enforce-fixed-action-hashes`
**Created**: 2026-08-02
**Status**: Approved

---

## User Scenarios & Testing

### User Story 1 - Secure GitHub Action Pinning (Priority: P1)

As a security architect, I want all GitHub Actions references in workflow files to use immutable 40-character SHA commit hashes instead of loose branch or tag references so that the CI/CD pipeline is protected from tag mutability and supply chain attacks.

**Why this priority**: Loose tags (e.g. `@v4`) can be repointed upstream, posing supply-chain attack risks.

**Independent Test**: Execute `pytest tests/test_github_workflows.py` to verify all GitHub Actions references across `.github/workflows/*.yml` are 40-character hex commit SHAs.

---

### User Story 2 - Automated Verification Gate (Priority: P1)

As a maintainer, I want `tests/test_github_workflows.py` to enforce that no unpinned or tag-based GitHub Action can be introduced in any workflow file.

---

## Requirements

### Functional Requirements

- **FR-001**: Every GitHub Action invocation (`uses: <owner>/<repo>[/subpath]@<ref>`) across all YAML files in `.github/workflows/` MUST specify a full 40-character hexadecimal commit SHA hash as its version reference.
- **FR-002**: Each pinned GitHub Action invocation MUST include an inline comment indicating the version tag or release label (e.g. `# v4.2.2`).
- **FR-003**: `tests/test_github_workflows.py` MUST contain an explicit unit test `test_all_github_actions_use_fixed_hashes` that scans all `.github/workflows/*.yml` files and fails if any action reference does not match a 40-hex-character SHA hash.

## Success Criteria

- **SC-001**: `pytest tests/test_github_workflows.py` passes 100% of tests including action hash validation.
- **SC-002**: Zero workflow steps in `.github/workflows/` use unpinned branch/tag references.
