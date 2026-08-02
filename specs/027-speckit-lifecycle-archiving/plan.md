# Architectural Plan: SpecKit Lifecycle and Archiving Integrations & Plugins

**Feature Branch**: `027-speckit-lifecycle-archiving`

**Created**: 2026-08-02

## Technical Architecture & Component Layout

```
.specify/
├── integrations/
│   ├── lifecycle.manifest.json
│   └── archive.manifest.json
├── scripts/powershell/
│   ├── lifecycle.ps1
│   └── archive-feature.ps1
└── workflows/
    └── workflow-registry.json (updated)

alos/
└── integrations/
    └── speckit/
        ├── __init__.py
        ├── lifecycle.py      # SpecKitLifecycleManager & state transition logic
        ├── archiver.py       # SpecKitArchiver & file/index operations
        └── plugins.py        # SpecKitPluginRegistry & hook dispatch

tests/
├── test_speckit_lifecycle_archiving.py
└── features/
    └── speckit_lifecycle_archiving.feature
```

## Data Models & Contracts

### `LifecycleState` (Enum)
- `DRAFT = "draft"`
- `IN_PROGRESS = "in_progress"`
- `APPROVED = "approved"`
- `COMPLETED = "completed"`
- `DEPRECATED = "deprecated"`
- `ARCHIVED = "archived"`

### State Transition Matrix
- `draft` → `in_progress`, `approved`, `deprecated`
- `in_progress` → `approved`, `draft`, `deprecated`
- `approved` → `completed`, `deprecated`
- `completed` → `archived`, `deprecated`
- `deprecated` → `archived`, `draft`
- `archived` → `draft`, `completed`

### `FeatureLifecycleRecord` (Pydantic Model)
- `feature_name`: str
- `current_state`: LifecycleState
- `history`: List[Dict[str, Any]]
- `updated_at`: str

### `ArchiveIndexRecord` (Pydantic Model)
- `feature_name`: str
- `archived_at`: str
- `original_path`: str
- `archive_path`: str
- `state_at_archive`: LifecycleState

## Quality Gate Validation

- `pytest`: 100% pass across unit and integration tests.
- `ruff check`: zero linting errors.
- `mypy`: clean type check.
- `bandit`: clean security scan.
