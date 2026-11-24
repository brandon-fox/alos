# Adopt Dual-Mode Portable Wheel and Hardened Container Production Runtime

* Status: accepted
* Deciders: Brandon Fox
* Date: 2026-11-23

Technical Story: `specs/034-portable-production-runtime/spec.md`

## Context and Problem Statement

Running ALOS previously required executing `uv run python -m ...` from inside a Git source checkout with working-directory-dependent paths (`./vault`, `./logs`), no installed console entry points (`[project.scripts]`), no single-instance daemon lock or `SIGTERM` handler, and a root-user `Dockerfile` lacking healthchecks or database migration assets. How do we make ALOS production-ready and portable across machines whether deployed as a standalone host install (for direct Windows NVML/Win32 hardware preemption) or as a hardened container/devcontainer?

## Decision Drivers

* **Relocatable Zero-Checkout Execution**: Ability to install `alos` and `alos-governor` from a built wheel (`uv tool install` / standalone venv) and run from any directory using a self-contained `ALOS_HOME` (`~/.alos` by default).
* **Dual Deployment Parity**: Identical CLI surface (`alos bootstrap`, `alos doctor`, `alos status`, `alos enqueue`, `alos tick`, `alos daemon`, `alos ledger`) across native portable installs and Docker containers.
* **Production Daemon Safety**: Single-instance PID lockfiles (reclaiming dead PIDs), `SIGTERM`/`SIGINT` graceful shutdown with guaranteed VRAM eviction, and atomic `health.json` heartbeats for container `HEALTHCHECK` and host supervisors.
* **Container Security & Thermal Isolation**: Non-root `UID 10001` multi-stage `Dockerfile`, CPU/RAM limits in `docker-compose.yml` and `.devcontainer/devcontainer.json`, and `host.docker.internal` bridging to host Ollama when containerized.

## Considered Options

* Option 1: Dual-mode portable wheel (`[project.scripts]` + `ALOS_HOME` runtime module) paired with a hardened non-root container & devcontainer stack
* Option 2: Container-only deployment requiring Docker Desktop for all invocations
* Option 3: PyInstaller single-file OS-specific frozen binaries only

## Decision Outcome

Chosen option: "Option 1: Dual-mode portable wheel (`[project.scripts]` + `ALOS_HOME` runtime module) paired with a hardened non-root container & devcontainer stack", because native portable installs retain zero-overhead Windows NVML and Direct3D gaming preemption on bare metal, while hardened containers and devcontainers provide reproducible Linux isolation for workers, CI, and multi-service Compose deployments.

### Positive Consequences

* One wheel artifact (`dist/alos-*.whl`) powers `uv tool install`, isolated portable directory installs (`scripts/install-portable.ps1`), Docker builds, and `.devcontainer` environments.
* `alos bootstrap` seeds default vault Markdown files from packaged resources and initializes SQLite/PostgreSQL tables without needing the Git repository present.
* `alos doctor` provides deterministic JSON readiness probes usable by humans, startup scripts, and Docker `HEALTHCHECK`.

### Negative Consequences

* Default template vault files must be bundled inside `alos/templates/` so wheel installs do not depend on repository-root `vault.example/`.
* Containerized workers running inside Linux WSL2 rely on host-bridged Ollama (`ALOS_SWARM_OLLAMA`) rather than Windows `user32.dll` HID hooks unless paired with the native host governor.

## Pros and Cons of the Options

### Option 1: Dual-mode portable wheel (`[project.scripts]` + `ALOS_HOME` runtime module) paired with a hardened non-root container & devcontainer stack

* Good, because Windows gaming rigs run `alos-governor daemon` natively with full `nvml.dll` + `SHQueryUserNotificationState` preemption while running isolated repos in `.devcontainer` or Compose.
* Good, because Linux/server or Docker-first users can run `docker compose --profile alos up -d` out of the box as an unprivileged user (`10001:10001`).
* Bad, because packaging data and host/container environment variables must be tested in both modes.

### Option 2: Container-only deployment requiring Docker Desktop for all invocations

* Good, because only one runtime OS target exists.
* Bad, because WSL2 `vmmemWSL` consumes multi-gigabyte host RAM even when idle and cannot read Win32 Direct3D fullscreen or HID idle state natively.

### Option 3: PyInstaller single-file OS-specific frozen binaries only

* Good, because no Python interpreter is needed on the target host.
* Bad, because bundling SQLAlchemy, LangGraph, CrewAI, and dynamic plugins into frozen binaries inflates artifact size (>250 MB) and complicates container deployment.

## Links

* Refines [ADR-0011](0011-adopt-dual-repo-open-source-architecture-and-public-ci-cd-pipeline.md)
* Refines [ADR-0015](0015-adopt-preemptible-host-governor-and-sticky-model-epoch-queue.md)
