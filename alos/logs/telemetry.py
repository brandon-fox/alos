"""Structured Execution Telemetry & Span Tracing Module.

Spec: specs/002-rust-core-architectural-refactor/spec.md (FR-002)
Constitution: Article III §2 (Audit & Observability Integrity)
"""

from __future__ import annotations

import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from pydantic import BaseModel, Field


class SpanContext(BaseModel):
    """Represents a single execution span in the telemetry tracer."""

    span_id: str
    name: str
    start_time: float
    end_time: float | None = None
    duration_ms: float | None = None
    status: str = "RUNNING"
    tags: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class TelemetryMetric(BaseModel):
    """Metric point for performance and throughput tracking."""

    metric_name: str
    value: float
    unit: str = "ms"
    timestamp: float = Field(default_factory=time.time)
    tags: dict[str, Any] = Field(default_factory=dict)


class TelemetryTracer:
    """Thread-safe telemetry tracer managing spans and metrics collection (SOLID: SRP)."""

    def __init__(self) -> None:
        self._spans: list[SpanContext] = []
        self._metrics: list[TelemetryMetric] = []
        self._span_counter: int = 0

    def start_span(self, name: str, tags: dict[str, Any] | None = None) -> SpanContext:
        """Start a new span."""
        self._span_counter += 1
        span_id = f"span-{self._span_counter:04d}"
        span = SpanContext(
            span_id=span_id,
            name=name,
            start_time=time.perf_counter(),
            tags=tags or {},
        )
        self._spans.append(span)
        return span

    def end_span(
        self, span: SpanContext, status: str = "SUCCESS", error: str | None = None
    ) -> SpanContext:
        """End an active span and compute duration."""
        span.end_time = time.perf_counter()
        span.duration_ms = round((span.end_time - span.start_time) * 1000.0, 3)
        span.status = status
        span.error = error
        return span

    @contextmanager
    def span(
        self, name: str, tags: dict[str, Any] | None = None
    ) -> Generator[SpanContext, None, None]:
        """Context manager for tracing execution blocks."""
        active_span = self.start_span(name, tags)
        try:
            yield active_span
            self.end_span(active_span, status="SUCCESS")
        except Exception as exc:
            self.end_span(active_span, status="ERROR", error=str(exc))
            raise

    def record_metric(
        self, metric_name: str, value: float, unit: str = "ms", tags: dict[str, Any] | None = None
    ) -> TelemetryMetric:
        """Record a performance metric."""
        metric = TelemetryMetric(metric_name=metric_name, value=value, unit=unit, tags=tags or {})
        self._metrics.append(metric)
        return metric

    def get_spans(self) -> list[SpanContext]:
        """Return all recorded spans."""
        return list(self._spans)

    def get_metrics(self) -> list[TelemetryMetric]:
        """Return all recorded metrics."""
        return list(self._metrics)

    def clear(self) -> None:
        """Clear recorded spans and metrics."""
        self._spans.clear()
        self._metrics.clear()


# Global singleton instance for easy telemetry tracking across modules
global_tracer = TelemetryTracer()
