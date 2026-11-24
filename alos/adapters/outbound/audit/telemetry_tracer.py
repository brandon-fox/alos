"""Driven telemetry adapter implementing TelemetryPort with W3C tracing & Prometheus export."""

import os
from typing import Any

from alos.config.settings import ALOSSettings
from alos.logs.telemetry import TelemetryTracer, get_active_span_context, global_tracer


class InMemoryTelemetryAdapter(TelemetryTracer):
    """Hexagonal Ring 3 TelemetryPort adapter preserving W3C spans and Prometheus metrics."""

    def observe_histogram(self, n: str, val: float, labels: Any = None, buckets: Any = None) -> Any:
        """Observe a value on a named histogram metric matching TelemetryPort."""
        return super().observe_histogram(n, val, labels=labels, buckets=buckets)


def _enrich_trace(out: dict[str, Any]) -> dict[str, Any]:
    sp = get_active_span_context()
    tid = out.get("trace_id") or (sp.trace_id if sp else None)
    return {**out, "trace_id": tid, "span_id": out.get("span_id") or (sp.span_id if sp else None)}


def _resolve_journal_path(explicit: str | None, attr: str, filename: str) -> str:
    cfg = ALOSSettings()
    fb = os.path.join(cfg.alos_home or os.getcwd(), "logs", filename)
    path = str(explicit or getattr(cfg, attr) or fb)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    return path


__all__ = ["InMemoryTelemetryAdapter", "TelemetryTracer", "global_tracer"]
