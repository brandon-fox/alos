# Feature Specification: Runtime Observability, Traceability, Metrics & Health Monitoring

**Feature Branch**: `feat/add-observability-metrics`
**Spec ID**: `031-runtime-observability-monitoring`
**Created**: 2026-11-24
**Status**: Approved
**Architecture Decision**: ADR-0014

## User Stories

- **US-1 (End-to-End Traceability)**: As an ALOS operator, I want W3C `traceparent`-compatible hierarchical spans (`trace_id`, `span_id`, `parent_span_id`) propagated across `ALOSStateGraph`, `EvaluatorNode`, `MCPGateway`, `BackgroundScheduler`, and `N8nSelfReflectionGraph`, and correlated into `logs/system_audit.jsonl` and `logs/decision_log.jsonl`, so every decision and mutation traces back to its originating execution.
- **US-2 (Runtime Metrics & Prometheus Exposition)**: As an SRE/maintainer, I want thread-safe counters, gauges, and latency histograms (`p50`, `p95`, `p99`) exported in Prometheus `0.0.4` text format and structured JSON snapshots so I can monitor throughput, error rates, token consumption, and safety-tier evaluations without external SaaS egress.
- **US-3 (Health Monitoring, SLO Alerts & Local Endpoint)**: As an operator running ALOS locally or in containers, I want cross-platform runtime health probes (`liveness`, `vault`, `audit_journals`, `native_bridge`), SLO threshold alerting, CLI inspection (`alos observability`), and a loopback-bound HTTP server (`/healthz`, `/readyz`, `/metrics`, `/traces`).

## Functional Requirements

- **FR-001**: `TelemetryTracer` MUST be thread-safe (`RLock`) and propagate active `(trace_id, span_id)` across nested calls via `contextvars`, supporting W3C `traceparent` (`00-<trace_id>-<span_id>-01`) formatting and parsing, span events, OpenTelemetry API (`opentelemetry.trace`) span bridging, and optional append-only JSONL persistence (`ALOS_TELEMETRY_LOG_PATH`).
- **FR-002**: `SystemAuditLogger` and `DecisionLogger` MUST automatically correlate active `trace_id` and `span_id` into audit and ADR decision records while preserving existing schema contracts and circular-import-free module initialization.
- **FR-003**: `TelemetryTracer` MUST support dimensional counters (`inc_counter`), gauges (`set_gauge`), and histograms (`observe_histogram` with configurable buckets and `p50`/`p95`/`p99` quantiles), plus Prometheus `0.0.4` text exposition (`render_prometheus`) and JSON snapshots (`snapshot`).
- **FR-004**: `ALOSStateGraph`, `EvaluatorNode`, `MCPGateway`, `BackgroundScheduler`, and `N8nSelfReflectionGraph` MUST emit hierarchical spans and runtime metrics via `TelemetryProtocol` (SOLID DIP), and `ALOSStateGraph.run()` MUST include `trace_id` in its response payload.
- **FR-005**: `RuntimeMonitor` MUST inspect process/runtime state (PID, uptime, memory RSS/Python heap, GC collections, active threads, native Rust bridge status), evaluate component readiness (`liveness`, `vault`, `audit_journals`, `native_bridge`), and emit `SLOAlert` warnings/criticals when latency or failure-rate thresholds (`ALOS_LATENCY_SLO_MS`, `ALOS_ERROR_RATE_THRESHOLD`) are breached.
- **FR-006**: `ObservabilityServer` MUST bind strictly to `127.0.0.1` by default (Constitution Article II) and serve `GET /healthz`, `GET /readyz` (`200` healthy/degraded, `503` unhealthy), `GET /metrics` (Prometheus text), and `GET /traces` (JSON spans).
- **FR-007**: `alos.cli` MUST expose `alos observability {health,metrics,traces,serve}` subcommands configured via `ALOSConfig` 12-Factor environment variables.
- **FR-008**: Spec-to-feature-to-ADR repository traceability (`docs/traceability.md`) MUST link `031-runtime-observability-monitoring` to its acceptance feature and `ADR-0014`.

## Non-Functional Requirements & Success Criteria

- **SC-001 (Local-First Privacy)**: Zero cloud telemetry egress by default; HTTP server binds to loopback unless explicitly overridden.
- **SC-002 (Code Quality & Complexity)**: All functions in `alos/` maintain Cyclomatic Complexity `CC <= 10` (below the `CC <= 12` AST gate), full MyPy typing, zero Bandit issues, and `>= 85%` test coverage.
