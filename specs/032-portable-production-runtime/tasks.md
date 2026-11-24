# Implementation Tasks: Portable & Containerized Production Runtime

**Spec**: [`specs/032-portable-production-runtime/spec.md`](spec.md)

---

- [x] **Task 1**: Propose and accept `ADR-0016` via `pyadr` and create SpecKit `032-portable-production-runtime`.
- [x] **Task 2**: Bundle default vault templates under `alos/templates/vault/` and configure `[project.scripts]` + package data in `pyproject.toml`.
- [x] **Task 3**: Implement `alos/runtime.py` (`RuntimePaths`, `SingleInstanceLock`, `HealthHeartbeat`, `bootstrap_home`, `run_doctor`, `query_ledger`).
- [x] **Task 4**: Wire `SIGTERM`/`SIGINT` handling, `SingleInstanceLock`, and `HealthHeartbeat` into `alos/swarm/queue.py` and unify operational subcommands in `alos/cli.py`.
- [x] **Task 5**: Harden `Dockerfile` (multi-stage, non-root `10001:10001`, `HEALTHCHECK`), add `alos-daemon` service to `docker-compose.yml`, add `.devcontainer/devcontainer.json`, create `scripts/install-portable.ps1`, and update `docs/getting_started.md`.
- [x] **Task 6**: Author unit tests (`tests/test_portable_runtime.py`) and `@mocked` + `@live` `behave` scenarios (`features/portable_runtime.feature`, `features/steps/portable_runtime_steps.py`) verifying out-of-tree wheel install and live Docker container execution.
- [x] **Task 7**: Pass full `.\scripts\run-validation-suite.ps1` and commit with SSH signatures.
