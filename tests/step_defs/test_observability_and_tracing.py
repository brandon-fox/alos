"""Step definitions for observability_and_tracing.feature."""

import time
from typing import Any

from pytest_bdd import given, parsers, scenarios, then, when

from alos.logs.telemetry import TelemetryTracer

scenarios("../features/observability_and_tracing.feature")


@given("an initialized TelemetryTracer instance")
def step_init_tracer(bdd_context: dict[str, Any]) -> None:
    tracer = TelemetryTracer()
    bdd_context["tracer"] = tracer


@when(parsers.parse('an execution span named "{span_name}" is executed'))
def step_execute_span(bdd_context: dict[str, Any], span_name: str) -> None:
    tracer: TelemetryTracer = bdd_context["tracer"]
    with tracer.span(span_name) as span:
        time.sleep(0.01)
        span.status = "SUCCESS"
    bdd_context["last_span_name"] = span_name


@then(parsers.parse('the tracer records a single span with status "{status}"'))
def step_records_span(bdd_context: dict[str, Any], status: str) -> None:
    tracer: TelemetryTracer = bdd_context["tracer"]
    spans = tracer.get_spans()
    assert len(spans) == 1
    assert spans[0].status == status


@then("the span duration is measured in milliseconds")
def step_duration_ms(bdd_context: dict[str, Any]) -> None:
    tracer: TelemetryTracer = bdd_context["tracer"]
    spans = tracer.get_spans()
    assert spans[0].duration_ms is not None
    assert spans[0].duration_ms >= 0


@when(parsers.parse('a metric named "{metric_name}" with value {val:f} is recorded'))
def step_record_metric(bdd_context: dict[str, Any], metric_name: str, val: float) -> None:
    tracer: TelemetryTracer = bdd_context["tracer"]
    tracer.record_metric(metric_name, val)
    bdd_context["metric_name"] = metric_name
    bdd_context["metric_val"] = val


@then("the metric is saved in the tracer metrics history")
def step_metric_saved(bdd_context: dict[str, Any]) -> None:
    tracer: TelemetryTracer = bdd_context["tracer"]
    metric_name = bdd_context["metric_name"]
    val = bdd_context["metric_val"]
    metrics = tracer.get_metrics()
    assert len(metrics) > 0
    assert any(m.metric_name == metric_name and m.value == val for m in metrics)
