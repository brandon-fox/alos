# Tasks: Runtime Observability, Traceability, Metrics & Health Monitoring

- [x] Task 1: Initialize SpecKit `031-runtime-observability-monitoring` artifacts and accept `ADR-0014` via `pyadr` (`FR-008`).
- [x] Task 2: Write failing BDD feature (`tests/features/runtime_observability_monitoring.feature`), step definitions, and TDD unit tests in `tests/test_sdd_bdd_features.py` covering `@mocked` and `@live` observability flows — verify RED (`FR-001`..`FR-007`).
- [x] Task 3: Fix `decision_log.py` circular import, add `TelemetryProtocol` and `ALOSConfig` settings, implement W3C hierarchical tracing, OpenTelemetry bridge, Prometheus metrics registry, and audit/decision trace correlation (`FR-001`, `FR-002`, `FR-003`).
- [x] Task 4: Implement `alos/logs/monitor.py` (`RuntimeMonitor`, readiness probes, SLO alerting, `ObservabilityServer` `/healthz`, `/readyz`, `/metrics`, `/traces`) (`FR-005`, `FR-006`).
- [x] Task 5: Instrument `ALOSStateGraph`, `EvaluatorNode`, `MCPGateway`, `BackgroundScheduler`, `N8nSelfReflectionGraph`, and `alos observability` CLI subcommands — verify GREEN (`FR-004`, `FR-007`).
- [x] Task 6: Regenerate `docs/traceability.md` and pass `ruff`, `mypy`, `bandit`, `pyadr check-adr-repo`, AST complexity, and `pytest --cov=alos` gates (`FR-008`, `SC-002`).
