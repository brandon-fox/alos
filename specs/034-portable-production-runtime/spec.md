# Feature Specification: Portable & Containerized Production Runtime

**Feature Branch**: `feat/preemptible-compute-governor`
**Created**: 2026-11-23
**Status**: Active
**Architecture Decisions**: [ADR-0018](../../docs/adr/0018-adopt-dual-mode-portable-wheel-and-hardened-container-production-runtime.md)

---

## Intent

Make ALOS portable, relocatable, and production-hardened so it can be installed and operated **outside a Git checkout** via **either** a standalone portable install (`uv tool` / relocatable wheel venv + `ALOS_HOME`) **or** a hardened non-root Docker container / devcontainer stack.

---

## Functional Requirements

- **FR-001 (Relocatable `ALOS_HOME` Runtime Layout)**: `alos.runtime.RuntimePaths` MUST resolve all runtime directories (`vault/`, `queue/`, `logs/`, `run/`) under `ALOS_HOME` (defaulting to `~/.alos`), eliminating working-directory dependence.
- **FR-002 (Self-Contained `bootstrap` Initialization)**: `alos bootstrap` MUST create the `ALOS_HOME` directory tree, seed missing `USER_PROFILE.md`, `PREFERENCES.md`, and `CORRECTION_LEDGER.md` files from package-bundled templates (`alos/templates/vault/`), write a default `alos.env` if absent, and initialize all SQLite/PostgreSQL database tables.
- **FR-003 (`doctor` Readiness & Container Health Probe)**: `alos doctor` MUST verify `ALOS_HOME` writability, database connectivity/tables, GPU/NVML availability, Ollama endpoint reachability + tier model presence, and Docker CLI availability, emitting structured JSON and deterministic exit codes (`0` when core runtime is healthy, non-zero when required checks fail).
- **FR-004 (Single-Instance Daemon Lock & Stale PID Recovery)**: `SingleInstanceLock` MUST acquire an exclusive PID lockfile (`run/governor.lock`) before `daemon` starts, rejecting duplicate live daemons with a clear error while automatically reclaiming stale lockfiles left by dead PIDs.
- **FR-005 (Graceful `SIGTERM`/`SIGINT` Shutdown & Atomic Health File)**: The standing `daemon` MUST handle `SIGTERM` and `SIGINT`, write atomic `run/health.json` heartbeats (`state`, `pid`, `active_tier`, `updated_at`, `status`), flush ledger state, and evict managed Ollama VRAM on shutdown.
- **FR-006 (Installed Console Entry Points)**: `pyproject.toml` MUST expose `[project.scripts]` (`alos`, `alos-governor`, `alos-dispatcher`, `alos-sandbox`), and `alos` MUST unify `bootstrap`, `doctor`, `status`, `enqueue`, `tick`, `daemon`, `ledger`, `crew`, `speckit`, and reasoning queries under one CLI.
- **FR-007 (Portable Installer & Optional Startup Registration)**: `scripts/install-portable.ps1` MUST build the wheel, install ALOS into a portable environment (`uv tool` or custom `-Prefix`), run `alos bootstrap` + `alos doctor`, and support opt-in Windows Scheduled Task registration (`-RegisterStartupTask` / `-UnregisterStartupTask`).
- **FR-008 (Hardened Non-Root Container & Devcontainer)**: `Dockerfile` MUST use a multi-stage build running as non-root `10001:10001` with `HEALTHCHECK` (`alos doctor --json`) and Alembic assets; `docker-compose.yml` MUST provide an `alos-daemon` service (`profiles: ["alos"]`) with CPU/RAM limits and `host.docker.internal` Ollama bridging; `.devcontainer/devcontainer.json` MUST define a resource-capped development container.

---

## Acceptance Scenarios

```gherkin
Feature: Portable Install and Hardened Container Production Runtime

  Scenario: Portable bootstrap seeds vault templates and database outside the repository
    Given an empty temporary ALOS_HOME directory outside the git repository
    When "alos bootstrap" is executed
    Then ALOS_HOME contains seeded vault Markdown files, logs, run directory, and initialized SQLite database
    And running "alos doctor --json" reports core runtime healthy with exit code 0

  Scenario: Single-instance lock blocks duplicate daemons and reclaims dead PID locks
    Given an active SingleInstanceLock held by the current process
    When a second SingleInstanceLock attempts to acquire the same lockfile
    Then acquisition fails naming the active holder PID
    When a lockfile contains a non-existent stale PID
    Then SingleInstanceLock reclaims the stale lockfile and succeeds

  Scenario: Installed wheel console scripts execute cleanly from an external directory
    Given a built ALOS wheel installed into an isolated virtual environment
    When "alos bootstrap", "alos doctor", "alos enqueue", and "alos tick" run from an external directory
    Then all commands exit 0 using ALOS_HOME without touching the git repository

  Scenario: Production Docker image runs non-root and passes bootstrap and doctor checks
    Given the production Dockerfile built as image "alos:local-prod"
    When a container runs "bootstrap" and "doctor --json" with an ephemeral /data volume
    Then the container runs as non-root UID 10001 and exits 0 with healthy runtime JSON
```
