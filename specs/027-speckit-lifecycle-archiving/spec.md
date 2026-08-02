# Feature Specification: SpecKit Lifecycle and Archiving Integrations & Plugins

**Feature Branch**: `027-speckit-lifecycle-archiving`

**Created**: 2026-08-02

**Status**: Approved

**Input**: User description: "Setup lifecycle and archiving integrations and plugins for speckit"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Spec Lifecycle Management (Priority: P1)

As a developer using SpecKit, I want to manage feature specification lifecycle states (`draft`, `in_progress`, `approved`, `completed`, `deprecated`, `archived`) so that the team can track specification status and enforce valid state transitions.

**Why this priority**: Core requirement for managing feature status across long-lived repositories.

**Independent Test**: Can be tested by invoking `SpecKitLifecycleManager` or `alos speckit lifecycle` to transition spec state and verify status persistence.

**Acceptance Scenarios**:

1. **Given** a spec in `draft` state, **When** transitioning to `approved`, **Then** the state updates to `approved` and status metadata is stored.
2. **Given** a spec in `draft` state, **When** attempting an invalid direct transition to `archived`, **Then** an invalid transition error is raised.

---

### User Story 2 - Automated Spec Archiving & Restoration (Priority: P2)

As a project maintainer, I want to archive completed or deprecated feature specifications into `specs/archive/` and restore them when needed, so that active `specs/` directories remain clean without losing history.

**Why this priority**: Maintains repository hygiene by moving inactive specs to an organized archive.

**Independent Test**: Can be tested by calling `SpecKitArchiver.archive_feature("027-speckit-lifecycle-archiving")` and verifying the spec is moved to `specs/archive/` with metadata index updated, and then restored.

**Acceptance Scenarios**:

1. **Given** a completed spec directory, **When** `SpecKitArchiver.archive_feature(...)` is called, **Then** the spec folder is moved to `specs/archive/<spec-name>/` and recorded in `specs/archive/archive-index.json`.
2. **Given** an archived spec directory, **When** `SpecKitArchiver.restore_feature(...)` is called, **Then** the spec folder is restored to `specs/<spec-name>/` and removed from `archive-index.json`.

---

### User Story 3 - SpecKit Plugin Registry & Integration Manifests (Priority: P3)

As an integration engineer, I want SpecKit integration manifests (`.specify/integrations/lifecycle.manifest.json`, `archive.manifest.json`) and a plugin registry (`SpecKitPluginRegistry`) so that external tools or custom scripts can hook into lifecycle events and archiving workflows.

**Why this priority**: Enables extensibility for custom hooks (e.g. n8n workflows, Slack notifications, GitHub Actions).

**Independent Test**: Can be tested by registering a custom plugin callback with `SpecKitPluginRegistry` and verifying it receives events during state transitions or archiving operations.

**Acceptance Scenarios**:

1. **Given** a registered plugin callback for `on_lifecycle_transition`, **When** a spec transitions state, **Then** the plugin hook function is executed with event metadata.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide `SpecKitLifecycleManager` supporting states `draft`, `in_progress`, `approved`, `completed`, `deprecated`, and `archived`.
- **FR-002**: System MUST enforce valid state transition matrix and reject invalid transitions with explicit exceptions.
- **FR-003**: System MUST provide `SpecKitArchiver` to archive completed or deprecated features into `specs/archive/` with an updated `archive-index.json`.
- **FR-004**: System MUST support restoring archived specs back to `specs/` via `SpecKitArchiver.restore_feature`.
- **FR-005**: System MUST provide `SpecKitPluginRegistry` allowing dynamic registration and execution of pre/post lifecycle and archiving hooks.
- **FR-006**: System MUST expose `alos speckit` CLI commands for lifecycle querying/transitions and archiving operations.

### Key Entities

- **LifecycleState**: Enum representing `DRAFT`, `IN_PROGRESS`, `APPROVED`, `COMPLETED`, `DEPRECATED`, `ARCHIVED`.
- **FeatureLifecycleRecord**: Data object containing spec path, current status, history of transitions, and updated timestamp.
- **ArchiveIndex**: Registry mapping archived feature IDs to archive timestamps, original path, and feature metadata.
- **SpecKitPlugin**: Interface or callable hook registered for event notifications (`pre_transition`, `post_transition`, `pre_archive`, `post_archive`).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of state transitions strictly follow valid state transition rules.
- **SC-002**: Archiving and restoring operations preserve all file contents, subdirectories, and checklists without data loss.
- **SC-003**: CLI commands execute lifecycle status checks and archiving in under 1 second.
- **SC-004**: Test suite achieves >90% code coverage on `alos.integrations.speckit` package.

## Assumptions

- Spec folders follow standard naming `specs/<N>-<feature-name>` or `specs/<feature-name>`.
- Python virtual environment is available with pytest, ruff, mypy, and bandit.
