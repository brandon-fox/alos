# Technical Execution Plan: Portable & Containerized Production Runtime

**Spec**: [`specs/032-portable-production-runtime/spec.md`](spec.md)
**ADR**: [ADR-0016](../../docs/adr/0016-adopt-dual-mode-portable-wheel-and-hardened-container-production-runtime.md)

---

## 1. Component Touchpoints

| File | Purpose |
| :--- | :--- |
| `alos/runtime.py` | `RuntimePaths` (`ALOS_HOME` resolution), `SingleInstanceLock` (cross-platform PID check + stale lock reclaim), `HealthHeartbeat` (`run/health.json` atomic write), `bootstrap_home()`, `run_doctor()`, `query_ledger()`. |
| `alos/templates/vault/*.md` | Bundled default `USER_PROFILE.md`, `PREFERENCES.md`, and `CORRECTION_LEDGER.md` packaged in wheel via `[tool.setuptools.package-data]`. |
| `alos/swarm/queue.py` | Wire `RuntimePaths`, `SingleInstanceLock`, `HealthHeartbeat`, and `SIGTERM`/`SIGINT` signal handling into `daemon` and CLI defaults. |
| `alos/cli.py` & `pyproject.toml` | Add `[project.scripts]` (`alos`, `alos-governor`, `alos-dispatcher`, `alos-sandbox`) and expose `bootstrap`, `doctor`, `status`, `enqueue`, `tick`, `daemon`, and `ledger` on `alos`. |
| `Dockerfile` & `.dockerignore` | Multi-stage `python:3.13-slim` wheel build, non-root `USER 10001:10001`, `ALOS_HOME=/data`, `HEALTHCHECK` via `alos doctor --json`. |
| `docker-compose.yml` & `.devcontainer/devcontainer.json` | Add `alos-daemon` service (`profiles: ["alos"]`, `cpus: 6.0`, `mem_limit: 8g`, `host.docker.internal` gateway) and portable VS Code / Antigravity devcontainer spec. |
| `scripts/install-portable.ps1` & `docs/getting_started.md` | One-command Windows portable installer (with optional scheduled startup task) and updated Getting Started documentation. |

---

## 2. Verification Plan

1. **Unit Suite (`tests/test_portable_runtime.py`)**: Fast unit tests for `RuntimePaths`, `SingleInstanceLock` (live PID contention + dead PID reclamation), `HealthHeartbeat`, `bootstrap_home` idempotency, `run_doctor`, `query_ledger`, and unified `alos` CLI subcommands (`CC <= 12`).
2. **Behave `@mocked` (`features/portable_runtime.feature`)**: End-to-end mocked scenarios for `bootstrap`, `doctor`, duplicate daemon lock rejection, `SIGTERM`/bounded daemon `health.json` lifecycle, and `ledger` output.
3. **Behave `@live` (`features/portable_runtime.feature`)**:
   - Build real wheel (`uv build`), install into an isolated venv outside the repo, execute `alos.exe bootstrap`, `alos.exe doctor`, `alos.exe enqueue`, `alos.exe tick`, and `alos.exe ledger` against live RTX 5080 NVML + Ollama.
   - Validate `docker compose config --quiet`, build real `Dockerfile` (`alos:local-prod`), verify non-root UID `10001`, and run `bootstrap` + `doctor` inside the live container.
