# Tasks: SpecKit Lifecycle and Archiving Integrations & Plugins

**Input**: Design documents from `/specs/027-speckit-lifecycle-archiving/`

## Phase 1: BDD Acceptance Tests & Pytest Test Suite setup (TDD RED Phase)

- [x] T001 [P] Create BDD feature file `tests/features/speckit_lifecycle_archiving.feature`
- [x] T002 [P] Create unit and integration test suite `tests/test_speckit_lifecycle_archiving.py`

## Phase 2: SpecKit Manifests & PowerShell Scripts

- [x] T003 [P] Create `.specify/integrations/lifecycle.manifest.json`
- [x] T004 [P] Create `.specify/integrations/archive.manifest.json`
- [x] T005 Update `.specify/workflows/workflow-registry.json`
- [x] T006 [P] Create `.specify/scripts/powershell/lifecycle.ps1`
- [x] T007 [P] Create `.specify/scripts/powershell/archive-feature.ps1`

## Phase 3: Python Integration Package (`alos/integrations/speckit/`)

- [x] T008 [P] Create `alos/integrations/speckit/__init__.py`
- [x] T009 Create `alos/integrations/speckit/lifecycle.py` (`SpecKitLifecycleManager`)
- [x] T010 Create `alos/integrations/speckit/archiver.py` (`SpecKitArchiver`)
- [x] T011 Create `alos/integrations/speckit/plugins.py` (`SpecKitPluginRegistry`)

## Phase 4: CLI Subcommand Integration

- [x] T012 Update `alos/cli.py` to add `alos speckit` CLI commands for `lifecycle` and `archive`

## Phase 5: Verification & Quality Audit (TDD GREEN Phase & Linting)

- [x] T013 Run pytest suite `uv run pytest tests/test_speckit_lifecycle_archiving.py`
- [x] T014 Run ruff, mypy, bandit, and full test suite
