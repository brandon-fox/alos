Feature: Stage 1 Telemetry Span Tracking and Observability Overlay

  Scenario: Telemetry Tracer Span Recording
    Given an initialized TelemetryTracer instance
    When an execution span named "context_assembly_span" is executed
    Then the tracer records a single span with status "SUCCESS"
    And the span duration is measured in milliseconds

  Scenario: Telemetry Tracer Metric Emission
    Given an initialized TelemetryTracer instance
    When a metric named "search_latency_ms" with value 2.45 is recorded
    Then the metric is saved in the tracer metrics history
