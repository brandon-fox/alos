# Quality Gate Checklist: Portable & Containerized Production Runtime (032)

- [x] `spec.md`, `plan.md`, `tasks.md`, and `checklists/requirements.md` complete under `specs/032-portable-production-runtime/`.
- [x] `ADR-0016` accepted and verified via `uv run pyadr check-adr-repo --no-ansi`.
- [x] `[project.scripts]` (`alos`, `alos-governor`, `alos-dispatcher`, `alos-sandbox`) build cleanly with `uv build` and `twine check`.
- [x] `SingleInstanceLock`, `SIGTERM` shutdown, `health.json`, `alos bootstrap`, and `alos doctor` verified in unit and `@mocked` + `@live` Behave suites.
- [x] Production `Dockerfile` runs as non-root `10001:10001`, includes `HEALTHCHECK`, and passes live container smoke + `docker compose config --quiet`.
- [x] All functions across `alos/` satisfy Cyclomatic Complexity `CC <= 12`, and `.\scripts\run-validation-suite.ps1` passes 100%.
