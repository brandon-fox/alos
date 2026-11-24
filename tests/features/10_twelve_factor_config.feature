# spec: 036-hexagonal-twelve-factor-refactor
Feature: Twelve-Factor Environment Configuration and Structured Stream Logging

  @mocked
  Scenario: Runtime settings, shims, and Factor XI stream logging work without import-time env mutation
    Given an isolated environment without CrewAI opt-out
    When settings, shims, and stream logging execute with env overrides
    Then import stays clean while runtime settings, shims, and stdout/stderr logging pass

  @live
  Scenario: Live .env resolution, SQLite DatabaseManager, Alembic env, and CLI script declaration
    Given a live .env pointing DATABASE_URL to SQLite
    When ALOSSettings, DatabaseManager, and Alembic run against SQLite
    Then SQLite persists records and pyproject declares deps and alos script
