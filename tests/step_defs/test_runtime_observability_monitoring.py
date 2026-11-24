"""BDD step definitions for runtime_observability_monitoring.feature (Spec 031)."""

from __future__ import annotations

import http.client
import json
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from alos.core.config import ALOSConfig
from alos.core.graph import ALOSStateGraph
from alos.logs.monitor import ObservabilityServer, RuntimeMonitor
from alos.logs.telemetry import TelemetryTracer

scenarios("../features/runtime_observability_monitoring.feature")


@given("a temporary vault and isolated TelemetryTracer for ALOSStateGraph")
def step_setup_traced_graph(bdd_context: dict[str, Any], tmp_vault: Path, tmp_path: Path) -> None:
    tracer = TelemetryTracer(log_file_path=str(tmp_path / "logs" / "telemetry.jsonl"))
    audit_path = tmp_path / "logs" / "system_audit.jsonl"
    decision_path = tmp_path / "logs" / "decision_log.jsonl"
    bdd_context["tracer"] = tracer
    bdd_context["audit_path"] = audit_path
    bdd_context["decision_path"] = decision_path
    bdd_context["graph"] = ALOSStateGraph(
        vault_dir=str(tmp_vault),
        audit_log_path=str(audit_path),
        decision_log_path=str(decision_path),
        tracer=tracer,
    )


@when('ALOSStateGraph executes the query "Schedule meeting Team Sync for today"')
def step_run_traced_graph(bdd_context: dict[str, Any]) -> None:
    graph: ALOSStateGraph = bdd_context["graph"]
    bdd_context["result"] = graph.run("Schedule meeting Team Sync for today")


@then("the execution result contains a valid 32-character W3C trace_id")
def step_verify_trace_id(bdd_context: dict[str, Any]) -> None:
    trace_id = bdd_context["result"].get("trace_id", "")
    assert isinstance(trace_id, str) and len(trace_id) == 32
    int(trace_id, 16)


@then(
    "child spans for context assembly, planning, evaluation, and MCP execution share that trace_id"
)
def step_verify_child_spans(bdd_context: dict[str, Any]) -> None:
    tracer: TelemetryTracer = bdd_context["tracer"]
    trace_id = bdd_context["result"]["trace_id"]
    spans = tracer.get_spans(trace_id=trace_id)
    names = {s.name for s in spans}
    assert "state_graph.run" in names
    assert "context.assemble" in names
    assert "planner.draft" in names
    assert "evaluator.evaluate" in names
    assert any(n.startswith("mcp.") for n in names)
    root = next(s for s in spans if s.name == "state_graph.run")
    children = [s for s in spans if s.span_id != root.span_id]
    assert all(c.parent_span_id is not None for c in children)
    assert root.traceparent.startswith(f"00-{trace_id}-")


@then("audit and decision log JSONL entries carry matching trace_id and span_id fields")
def step_verify_log_correlation(bdd_context: dict[str, Any]) -> None:
    trace_id = bdd_context["result"]["trace_id"]
    audit_lines = bdd_context["audit_path"].read_text(encoding="utf-8").strip().splitlines()
    decision_lines = bdd_context["decision_path"].read_text(encoding="utf-8").strip().splitlines()
    for raw in [*audit_lines, *decision_lines]:
        rec = json.loads(raw)
        assert rec["trace_id"] == trace_id
        assert isinstance(rec["span_id"], str) and len(rec["span_id"]) == 16


@given("an isolated TelemetryTracer recording counters, gauges, and latency observations")
def step_setup_metrics_tracer(bdd_context: dict[str, Any]) -> None:
    tracer = TelemetryTracer()
    tracer.inc_counter("alos_agent_runs_total", labels={"status": "SUCCESS"})
    tracer.inc_counter("alos_agent_runs_total", amount=2.0, labels={"status": "SUCCESS"})
    tracer.set_gauge("alos_active_spans", 1.0)
    for sample in (5.0, 10.0, 25.0, 50.0, 120.0):
        tracer.observe_histogram(
            "alos_agent_run_duration_ms", sample, labels={"component": "graph"}
        )
    bdd_context["tracer"] = tracer


@when("Prometheus text exposition is rendered")
def step_render_prometheus(bdd_context: dict[str, Any]) -> None:
    tracer: TelemetryTracer = bdd_context["tracer"]
    bdd_context["prom_text"] = tracer.render_prometheus()


@then("the exposition contains HELP and TYPE headers for counters, gauges, and histograms")
def step_verify_prom_headers(bdd_context: dict[str, Any]) -> None:
    prom: str = bdd_context["prom_text"]
    assert "# TYPE alos_agent_runs_total counter" in prom
    assert 'alos_agent_runs_total{status="SUCCESS"} 3.0' in prom
    assert "# TYPE alos_active_spans gauge" in prom
    assert "# TYPE alos_agent_run_duration_ms histogram" in prom
    assert 'alos_agent_run_duration_ms_count{component="graph"} 5' in prom


@then("histogram summaries expose accurate p50, p95, and p99 quantiles")
def step_verify_quantiles(bdd_context: dict[str, Any]) -> None:
    tracer: TelemetryTracer = bdd_context["tracer"]
    summary = tracer.get_histogram("alos_agent_run_duration_ms", labels={"component": "graph"})
    assert summary is not None
    assert summary.count == 5
    assert summary.p50 == 25.0
    assert summary.p95 >= 50.0
    assert summary.p99 >= 50.0


@given("a live ObservabilityServer bound to an ephemeral loopback port")
def step_start_live_server(
    bdd_context: dict[str, Any],
    tmp_vault: Path,
    tmp_path: Path,
    request: pytest.FixtureRequest,
) -> None:
    config = ALOSConfig(latency_slo_ms=10.0, error_rate_threshold=0.2)
    tracer = TelemetryTracer()
    monitor = RuntimeMonitor(
        config=config,
        tracer=tracer,
        vault_dir=str(tmp_vault),
        log_dir=str(tmp_path / "logs"),
    )
    server = ObservabilityServer(monitor=monitor, tracer=tracer, host="127.0.0.1", port=0)
    host, port = server.start()
    assert server.start() == (host, port)
    request.addfinalizer(server.stop)
    bdd_context["server"] = server
    bdd_context["tracer"] = tracer
    bdd_context["host"] = host
    bdd_context["port"] = port


@when("runtime spans breach the configured latency SLO threshold")
def step_breach_slo(bdd_context: dict[str, Any]) -> None:
    tracer: TelemetryTracer = bdd_context["tracer"]
    for val in (25.0, 30.0, 45.0):
        tracer.observe_histogram("alos_span_duration_ms", val, labels={"span_name": "slow_op"})


@then('live HTTP GET requests to "/healthz", "/readyz", "/metrics", and "/traces" succeed')
def step_fetch_live_endpoints(bdd_context: dict[str, Any]) -> None:
    host: str = bdd_context["host"]
    port: int = bdd_context["port"]
    with bdd_context["tracer"].span("live_probe_span"):
        pass
    responses: dict[str, str] = {}
    for endpoint in ("/healthz", "/readyz", "/metrics", "/traces"):
        conn = http.client.HTTPConnection(host, port, timeout=5)
        try:
            conn.request("GET", endpoint)
            resp = conn.getresponse()
            assert resp.status == 200
            responses[endpoint] = resp.read().decode("utf-8")
        finally:
            conn.close()
    bdd_context["http_responses"] = responses


@then('the "/readyz" health report surfaces a latency SLO alert and runtime process telemetry')
def step_verify_readyz_payload(bdd_context: dict[str, Any]) -> None:
    responses: dict[str, str] = bdd_context["http_responses"]
    ready = json.loads(responses["/readyz"])
    assert ready["status"] in ("DEGRADED", "HEALTHY")
    assert ready["runtime"]["pid"] > 0
    assert any("latency" in a["metric"] or "duration" in a["metric"] for a in ready["alerts"])
    assert "alos_process_uptime_seconds" in responses["/metrics"]
    traces = json.loads(responses["/traces"])
    assert any(t["name"] == "live_probe_span" for t in traces)
