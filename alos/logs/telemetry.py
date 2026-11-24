"""Structured Execution Telemetry, W3C Trace Propagation & Prometheus Metrics Registry.

Spec: specs/003-rust-core-architectural-refactor/spec.md (FR-002),
      specs/031-runtime-observability-monitoring/spec.md (FR-001, FR-003)
Constitution: Article II (Local-First Privacy), Article III §2 (Audit & Observability Integrity)
"""

from __future__ import annotations

import json
import math
import os
import re
import threading
import time
import uuid
from collections import defaultdict
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from opentelemetry import trace as otel_trace
from pydantic import BaseModel, Field

TRACEPARENT_RE = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-[0-9a-f]{2}$")
DEFAULT_BUCKETS: tuple[float, ...] = (
    1.0,
    5.0,
    10.0,
    25.0,
    50.0,
    100.0,
    250.0,
    500.0,
    1000.0,
    2500.0,
)
LabelTuple = tuple[tuple[str, str], ...]
MetricKey = tuple[str, LabelTuple]


class SpanContext(BaseModel):
    """Represents a hierarchical execution span with W3C Trace Context metadata."""

    trace_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    span_id: str
    parent_span_id: str | None = None
    name: str
    start_time: float
    end_time: float | None = None
    duration_ms: float | None = None
    status: str = "RUNNING"
    tags: dict[str, Any] = Field(default_factory=dict)
    events: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None

    @property
    def traceparent(self) -> str:
        """Format span context as a W3C traceparent header value."""
        return f"00-{self.trace_id}-{self.span_id}-01"

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        """Attach a timestamped breadcrumb event to this span."""
        self.events.append(
            {"name": name, "timestamp": time.time(), "attributes": dict(attributes or {})}
        )


class TelemetryMetric(BaseModel):
    """Metric point for performance and throughput tracking."""

    metric_name: str
    value: float
    unit: str = "ms"
    timestamp: float = Field(default_factory=time.time)
    tags: dict[str, Any] = Field(default_factory=dict)


class HistogramSummary(BaseModel):
    """Aggregated summary statistics and quantiles for a histogram series."""

    count: int
    sum: float
    min: float
    max: float
    p50: float
    p95: float
    p99: float
    buckets: dict[str, int]


_ACTIVE_SPAN: ContextVar[SpanContext | None] = ContextVar("alos_active_span", default=None)


def get_active_span_context() -> SpanContext | None:
    """Return the active SpanContext in the current execution context, if any."""
    return _ACTIVE_SPAN.get()


def parse_traceparent(header: str) -> tuple[str, str] | None:
    """Parse a W3C traceparent header into (trace_id, parent_span_id), or None if invalid."""
    match = TRACEPARENT_RE.match(header.strip().lower())
    if not match:
        return None
    trace_id, parent_span_id = match.group(1), match.group(2)
    if trace_id == "0" * 32 or parent_span_id == "0" * 16:
        return None
    return trace_id, parent_span_id


def _label_key(labels: dict[str, str] | None) -> LabelTuple:
    return tuple(sorted((str(k), str(v)) for k, v in (labels or {}).items()))


def _escape_label(val: str) -> str:
    return val.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _format_labels(labels: LabelTuple) -> str:
    if not labels:
        return ""
    inner = ",".join(f'{k}="{_escape_label(v)}"' for k, v in labels)
    return f"{{{inner}}}"


def _quantile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = min(len(sorted_vals) - 1, max(0, math.ceil(q * len(sorted_vals)) - 1))
    return round(sorted_vals[idx], 3)


def _summarize_samples(samples: list[float], buckets: tuple[float, ...]) -> HistogramSummary:
    if not samples:
        return HistogramSummary(
            count=0, sum=0.0, min=0.0, max=0.0, p50=0.0, p95=0.0, p99=0.0, buckets={}
        )
    ordered = sorted(samples)
    bucket_counts = {str(b): sum(1 for v in ordered if v <= b) for b in buckets}
    bucket_counts["+Inf"] = len(ordered)
    return HistogramSummary(
        count=len(ordered),
        sum=round(sum(ordered), 3),
        min=round(ordered[0], 3),
        max=round(ordered[-1], 3),
        p50=_quantile(ordered, 0.50),
        p95=_quantile(ordered, 0.95),
        p99=_quantile(ordered, 0.99),
        buckets=bucket_counts,
    )


def _render_simple_family(metric_type: str, store: dict[MetricKey, float]) -> list[str]:
    grouped: dict[str, list[tuple[LabelTuple, float]]] = defaultdict(list)
    for (name, ltuple), val in sorted(store.items()):
        grouped[name].append((ltuple, val))
    lines: list[str] = []
    for name, series in grouped.items():
        lines.append(f"# HELP {name} ALOS runtime {metric_type} {name}")
        lines.append(f"# TYPE {name} {metric_type}")
        for ltuple, val in series:
            lines.append(f"{name}{_format_labels(ltuple)} {val}")
    return lines


def _render_histograms(
    store: dict[MetricKey, list[float]], bucket_cfg: dict[str, tuple[float, ...]]
) -> list[str]:
    grouped: dict[str, list[tuple[LabelTuple, list[float]]]] = defaultdict(list)
    for (name, ltuple), vals in sorted(store.items()):
        grouped[name].append((ltuple, vals))
    lines: list[str] = []
    for name, series in grouped.items():
        lines.append(f"# HELP {name} ALOS runtime histogram {name}")
        lines.append(f"# TYPE {name} histogram")
        buckets = bucket_cfg.get(name, DEFAULT_BUCKETS)
        for ltuple, vals in series:
            summary = _summarize_samples(vals, buckets)
            for bound, count in summary.buckets.items():
                b_labels = _format_labels((*ltuple, ("le", bound)))
                lines.append(f"{name}_bucket{b_labels} {count}")
            lbl = _format_labels(ltuple)
            lines.append(f"{name}_sum{lbl} {summary.sum}")
            lines.append(f"{name}_count{lbl} {summary.count}")
    return lines


class TelemetryTracer:
    """Thread-safe telemetry tracer and Prometheus metrics registry (SOLID: SRP & DIP)."""

    def __init__(self, log_file_path: str | None = None, enabled: bool = True) -> None:
        self.log_file_path = log_file_path
        self.enabled = enabled
        self._lock = threading.RLock()
        self._spans: list[SpanContext] = []
        self._metrics: list[TelemetryMetric] = []
        self._counters: dict[MetricKey, float] = {}
        self._gauges: dict[MetricKey, float] = {}
        self._histograms: dict[MetricKey, list[float]] = {}
        self._histogram_buckets: dict[str, tuple[float, ...]] = {}
        self._active_count: int = 0
        if self.log_file_path:
            os.makedirs(os.path.dirname(os.path.abspath(self.log_file_path)), exist_ok=True)

    def _resolve_lineage(
        self, trace_id: str | None, parent_span_id: str | None, traceparent: str | None
    ) -> tuple[str, str | None]:
        if traceparent:
            parsed = parse_traceparent(traceparent)
            if parsed:
                return parsed
        active = get_active_span_context()
        if trace_id:
            return trace_id, parent_span_id or (active.span_id if active else None)
        if active:
            return active.trace_id, parent_span_id or active.span_id
        return uuid.uuid4().hex, parent_span_id

    def _append_jsonl(self, payload: dict[str, Any]) -> None:
        if not self.log_file_path or not self.enabled:
            return
        with open(self.log_file_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload) + "\n")

    def start_span(
        self,
        name: str,
        tags: dict[str, Any] | None = None,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        traceparent: str | None = None,
    ) -> SpanContext:
        """Start a new hierarchical execution span."""
        resolved_trace, resolved_parent = self._resolve_lineage(
            trace_id, parent_span_id, traceparent
        )
        span = SpanContext(
            trace_id=resolved_trace,
            span_id=uuid.uuid4().hex[:16],
            parent_span_id=resolved_parent,
            name=name,
            start_time=time.perf_counter(),
            tags=dict(tags or {}),
        )
        with self._lock:
            self._spans.append(span)
            self._active_count += 1
            self._gauges[("alos_active_spans", ())] = float(self._active_count)
        return span

    def end_span(
        self, span: SpanContext, status: str = "SUCCESS", error: str | None = None
    ) -> SpanContext:
        """End an active span, record duration histogram, and persist if configured."""
        with self._lock:
            span.end_time = time.perf_counter()
            span.duration_ms = round((span.end_time - span.start_time) * 1000.0, 3)
            span.status = status
            span.error = error
            self._active_count = max(0, self._active_count - 1)
            self._gauges[("alos_active_spans", ())] = float(self._active_count)
            self.observe_histogram(
                "alos_span_duration_ms",
                span.duration_ms,
                labels={"span_name": span.name, "status": status},
            )
            self._append_jsonl({"record_type": "span", **span.model_dump()})
        return span

    @contextmanager
    def span(
        self,
        name: str,
        tags: dict[str, Any] | None = None,
        traceparent: str | None = None,
    ) -> Generator[SpanContext, None, None]:
        """Context manager propagating active SpanContext and bridging OpenTelemetry API."""
        active_span = self.start_span(name, tags=tags, traceparent=traceparent)
        token = _ACTIVE_SPAN.set(active_span)
        otel_tracer = otel_trace.get_tracer("alos.runtime")
        try:
            with otel_tracer.start_as_current_span(name) as otel_span:
                for key, val in active_span.tags.items():
                    if isinstance(val, bool | int | float | str):
                        otel_span.set_attribute(key, val)
                yield active_span
            self.end_span(active_span, status="SUCCESS")
        except Exception as exc:
            self.end_span(active_span, status="ERROR", error=str(exc))
            raise
        finally:
            _ACTIVE_SPAN.reset(token)

    def record_metric(
        self, metric_name: str, value: float, unit: str = "ms", tags: dict[str, Any] | None = None
    ) -> TelemetryMetric:
        """Record a point metric and persist if JSONL sink is configured."""
        metric = TelemetryMetric(
            metric_name=metric_name, value=value, unit=unit, tags=dict(tags or {})
        )
        with self._lock:
            self._metrics.append(metric)
            self._append_jsonl({"record_type": "metric", **metric.model_dump()})
        return metric

    def inc_counter(
        self, name: str, amount: float = 1.0, labels: dict[str, str] | None = None
    ) -> float:
        """Increment a dimensional counter metric."""
        key = (name, _label_key(labels))
        with self._lock:
            new_val = self._counters.get(key, 0.0) + amount
            self._counters[key] = new_val
            return new_val

    def set_gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> float:
        """Set a dimensional gauge metric."""
        key = (name, _label_key(labels))
        with self._lock:
            self._gauges[key] = float(value)
            return float(value)

    def observe_histogram(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
        buckets: tuple[float, ...] | None = None,
    ) -> HistogramSummary:
        """Record an observation in a dimensional histogram series."""
        key = (name, _label_key(labels))
        with self._lock:
            if buckets is not None:
                self._histogram_buckets[name] = buckets
            bucket_bounds = self._histogram_buckets.get(name, DEFAULT_BUCKETS)
            series = self._histograms.setdefault(key, [])
            series.append(float(value))
            return _summarize_samples(series, bucket_bounds)

    def get_counter(self, name: str, labels: dict[str, str] | None = None) -> float:
        """Read current value of a counter series."""
        with self._lock:
            return self._counters.get((name, _label_key(labels)), 0.0)

    def get_gauge(self, name: str, labels: dict[str, str] | None = None) -> float:
        """Read current value of a gauge series."""
        with self._lock:
            return self._gauges.get((name, _label_key(labels)), 0.0)

    def get_histogram(
        self, name: str, labels: dict[str, str] | None = None
    ) -> HistogramSummary | None:
        """Return aggregated HistogramSummary for a series, or None if unrecorded."""
        key = (name, _label_key(labels))
        with self._lock:
            samples = self._histograms.get(key)
            if samples is None:
                return None
            return _summarize_samples(samples, self._histogram_buckets.get(name, DEFAULT_BUCKETS))

    def get_all_histograms(self) -> dict[str, HistogramSummary]:
        """Return summaries keyed by formatted series identifier across all histograms."""
        with self._lock:
            return {
                f"{name}{_format_labels(ltuple)}": _summarize_samples(
                    vals, self._histogram_buckets.get(name, DEFAULT_BUCKETS)
                )
                for (name, ltuple), vals in self._histograms.items()
            }

    def render_prometheus(self) -> str:
        """Render all counters, gauges, and histograms in Prometheus 0.0.4 text format."""
        with self._lock:
            lines = [
                *_render_simple_family("counter", self._counters),
                *_render_simple_family("gauge", self._gauges),
                *_render_histograms(self._histograms, self._histogram_buckets),
            ]
        return ("\n".join(lines) + "\n") if lines else ""

    def snapshot(self) -> dict[str, Any]:
        """Export structured JSON-serializable snapshot of metrics and span counts."""
        with self._lock:
            return {
                "counters": {
                    f"{n}{_format_labels(lbl)}": v for (n, lbl), v in self._counters.items()
                },
                "gauges": {f"{n}{_format_labels(lbl)}": v for (n, lbl), v in self._gauges.items()},
                "histograms": {k: v.model_dump() for k, v in self.get_all_histograms().items()},
                "span_count": len(self._spans),
                "active_spans": self._active_count,
            }

    def get_spans(self, limit: int | None = None, trace_id: str | None = None) -> list[SpanContext]:
        """Return recorded spans, optionally filtered by trace_id and capped by limit."""
        with self._lock:
            items = [s for s in self._spans if trace_id is None or s.trace_id == trace_id]
            return items[-limit:] if limit is not None else list(items)

    def get_metrics(self) -> list[TelemetryMetric]:
        """Return all recorded point metrics."""
        with self._lock:
            return list(self._metrics)

    def clear(self) -> None:
        """Reset all recorded spans, point metrics, counters, gauges, and histograms."""
        with self._lock:
            self._spans.clear()
            self._metrics.clear()
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._active_count = 0


# Global singleton instance for default runtime observability
global_tracer = TelemetryTracer()
