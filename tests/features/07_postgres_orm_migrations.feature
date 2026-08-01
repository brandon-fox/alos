Feature: PostgreSQL ORM Models and Alembic Migration Infrastructure
  As an ALOS developer and operator
  I want database tables and migrations managed via SQLAlchemy 2.0 ORM and Alembic
  So that schema evolution is deterministic, type-safe, version-controlled, and reproducible.

  Scenario: Define SQLAlchemy 2.0 ORM domain models
    Given declarative Base model in alos.db.base
    When AuditLogModel, DecisionRecordModel, ExecutionStateModel, and UserProfileModel are instantiated
    Then model attributes must map correctly to relational column definitions and primary keys

  Scenario: Execute Alembic migration upgrade and downgrade programmatically
    Given alembic.ini configuration bound to alos.db.base.Base.metadata
    When alembic upgrade head and downgrade base commands run
    Then database schema migrations must execute reproducibly without errors
