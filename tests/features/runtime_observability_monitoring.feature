# spec: 031-runtime-observability-monitoring
Feature: End-to-End Runtime Traceability, Prometheus Metrics, and Health Monitoring

  @mocked
  Scenario: Hierarchical trace propagation and audit-decision log correlation
    Given a temporary vault and isolated TelemetryTracer for ALOSStateGraph
    When ALOSStateGraph executes the query "Schedule meeting Team Sync for today"
    Then the execution result contains a valid 32-character W3C trace_id
    And child spans for context assembly, planning, evaluation, and MCP execution share that trace_id
    And audit and decision log JSONL entries carry matching trace_id and span_id fields

  @mocked
  Scenario: Dimensional counters, gauges, histograms, and Prometheus exposition
    Given an isolated TelemetryTracer recording counters, gauges, and latency observations
    When Prometheus text exposition is rendered
    Then the exposition contains HELP and TYPE headers for counters, gauges, and histograms
    And histogram summaries expose accurate p50, p95, and p99 quantiles

  @live
  Scenario: Runtime health monitor SLO alerting and live loopback HTTP endpoints
    Given a live ObservabilityServer bound to an ephemeral loopback port
    When runtime spans breach the configured latency SLO threshold
    Then live HTTP GET requests to "/healthz", "/readyz", "/metrics", and "/traces" succeed
    And the "/readyz" health report surfaces a latency SLO alert and runtime process telemetry
