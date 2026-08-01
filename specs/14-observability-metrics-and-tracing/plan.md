# Architecture Plan: Observability, Metrics & Tracing (Spec 14)

```mermaid
graph TD
    Graph[ALOS Engine] --> OTel[OpenTelemetry Tracer]
    Graph --> Prom[Prometheus Metrics]
    Graph --> Audit[SystemAuditLogger]
    OTel --> Collector[OTel Collector / Sentry]
```

- Instrument `ALOSStateGraph.run()` with OpenTelemetry spans (`tracer.start_as_current_span`).
- Expose Prometheus metrics counter `alos_actions_total{status="approved"}`.
