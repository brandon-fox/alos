# Feature Specification: CI PyADR Verification & Health Gate (Spec 001)

**Feature Branch**: `001-fix-ci-pyadr`
**Created**: 2026-08-01
**Status**: Approved

## User Stories & Functional Requirements

### User Story 1: Mandatory ADR Validation Gate
- **As a** repository maintainer and AI agent,
- **I want** GitHub Actions and local pre-commit hooks to run `pyadr check-adr-repo -n` automatically,
- **So that** broken ADR numbering, formatting, or unindexed ADRs never land on `main`.

## Functional Requirements
- **FR-001-01**: The system MUST execute `pyadr check-adr-repo -n` during pre-commit and CI validation runs.
- **FR-001-02**: Any failure in `pyadr check-adr-repo` MUST cause CI pre-commit and pre-push quality gates to fail.
- **FR-001-03**: All ADRs created in `docs/adr/` MUST trace to valid sequential headers and be indexed in `docs/adr/index.md`.

## Acceptance Criteria
1. Running `pyadr check-adr-repo -n` returns exit code 0 on valid ADR repositories.
2. CI workflow `.github/workflows/ci.yml` includes a mandatory `pyadr check-adr-repo` step.
