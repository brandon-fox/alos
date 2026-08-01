# Spec 07 — PostgreSQL ORM & Migration Infrastructure

## User Story
As an ALOS developer and operator, I need all PostgreSQL data models, schema definitions, and schema migrations to be strictly managed through an ORM (SQLAlchemy 2.0) with tracked, version-controlled, and repeatable migrations (Alembic), so that schema evolution is deterministic, audit-logged, reproducible across environments, and fully integrated with python type safety.

## Acceptance Criteria
1. **ORM-Driven Schema Definition**: All PostgreSQL database tables, relationships, indexes, and field constraints MUST be declared using SQLAlchemy 2.0 Declarative ORM models under `alos.db.models`.
2. **Version-Controlled Migrations**: Database schema changes MUST be generated and tracked as versioned revision scripts in `alembic/versions/`.
3. **Repeatable Migration Execution**: Schema upgrades (`alembic upgrade head`) and downgrades (`alembic downgrade base`) MUST execute programmatically and via CLI repeatably without manual SQL execution.
4. **Migration Version State**: Migration execution status MUST be tracked in the target database using the standard `alembic_version` schema table.

## Requirements
- **FR-07-01**: `alos.db.base.Base` serves as the declarative base for all ORM domain models.
- **FR-07-02**: Core ALOS data entities (`AuditLog`, `DecisionRecord`, `ExecutionState`, `UserProfile`) MUST be defined as SQLAlchemy ORM classes.
- **FR-07-03**: `alembic.ini` and `alembic/env.py` MUST bind to `alos.db.base.Base.metadata` for automated migration generation and execution.
- **FR-07-04**: An initial baseline migration script (`0001_initial_postgres_schema.py`) MUST be checked into version control.
