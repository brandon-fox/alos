# Feature Specification: Open-Source Core & Dual-Repo Architecture

## 1. Executive Summary
This specification defines the architectural model for decoupling the ALOS open-source core framework (`alos`) from personal private setups (n8n JSON workflows, Obsidian vault notes, local environment secrets, and custom execution hooks). It establishes GitHub Actions CI workflows for free public integration testing and standardizes open-source repository templates.

---

## 2. User Stories & Acceptance Criteria

### User Story 1: Open Source Contributor
* **As an** open source developer or contributor,
* **I want** to clone the public `alos` repository, install dependencies with `uv`, and run linting/testing quality gates out of the box using template data,
* **So that** I can contribute to the ALOS core engine without needing access to private user environments or credentials.

### User Story 2: Privacy-Conscious End User
* **As an** ALOS end user,
* **I want** to maintain my personal workflows, Obsidian vault memory, and `.env` secrets in a separate private GitHub repository,
* **So that** I can version-control my personal automation logic without risking accidental leakage of sensitive credentials or private notes.

### User Story 3: Continuous Integration (GitHub Actions)
* **As a** repository maintainer,
* **I want** GitHub Actions to run unit tests, ruff lint checks, and mypy type checks automatically on every PR,
* **So that** code quality and safety gates are strictly maintained.

---

## 3. Functional & Technical Requirements

1. **Configurable Workflow Directory (`ALOS_WORKFLOWS_DIR`)**:
   - `ALOSConfig` must read `ALOS_WORKFLOWS_DIR` from environment variables, defaulting to `"workflows"`.
2. **Template Directories (`vault.example/` & `workflows.example/`)**:
   - Baseline mock profiles (`USER_PROFILE.md`, `PREFERENCES.md`, `CORRECTION_LEDGER.md`) must be provided under `vault.example/`.
   - Baseline n8n workflow JSON templates (`wf-human-approval-gate.json`, `wf-health-poll-self-correct.json`, `wf-vault-knowledge-ingestion.json`) must be provided under `workflows.example/`.
3. **Environment Template (`.env.example`)**:
   - Comprehensive `.env.example` file documenting all required database keys, API tokens, n8n encryption key, and path configurations.
4. **License & Overlay Files**:
   - Permissive MIT license file (`LICENSE`).
   - Sample `docker-compose.override.yml.example` for mounting private host volumes.
5. **Git Hygiene**:
   - Update `.gitignore` so local working `vault/` and `workflows/` directories stay ignored while template directories remain tracked.
