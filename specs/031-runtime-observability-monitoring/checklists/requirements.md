# Requirements Checklist: Runtime Observability, Traceability, Metrics & Health Monitoring

- [x] **FR-001**: Thread-safe W3C hierarchical tracing (`trace_id`, `span_id`, `parent_span_id`, `traceparent`), OTel API bridge, and optional JSONL span persistence.
- [x] **FR-002**: Automatic `trace_id`/`span_id` correlation in `SystemAuditLogger` and `DecisionLogger` without circular imports.
- [x] **FR-003**: Counters, gauges, and histograms (`p50`/`p95`/`p99`) with Prometheus `0.0.4` text exposition and JSON snapshots.
- [x] **FR-004**: Runtime span and metric instrumentation across `ALOSStateGraph`, `EvaluatorNode`, `MCPGateway`, `BackgroundScheduler`, and `N8nSelfReflectionGraph`.
- [x] **FR-005**: `RuntimeMonitor` process stats, readiness probes (`liveness`, `vault`, `audit_journals`, `native_bridge`), and SLO breach alerts.
- [x] **FR-006**: Loopback-bound `ObservabilityServer` serving `/healthz`, `/readyz`, `/metrics`, and `/traces`.
- [x] **FR-007**: `alos observability {health,metrics,traces,serve}` CLI subcommands and `ALOSConfig` env configuration.
- [x] **FR-008**: Updated `docs/traceability.md` linking Spec `031`, Gherkin feature, and `ADR-0014`, passing all quality gates.
