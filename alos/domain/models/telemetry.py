"""Pure domain telemetry models and W3C Trace Context parsing helpers.

Ring 1 (Pure Domain): stdlib + pydantic only (no opentelemetry SDK imports; FR-3604).
"""

from __future__ import annotations

import re
import time
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

TRACEPARENT_RE = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-[0-9a-f]{2}$")


class SpanContext(BaseModel):
    """Execution span with W3C Trace Context metadata and assignment validation (non-frozen)."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    trace_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    span_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    parent_span_id: str | None = None
    name: str
    start_time: float = Field(default_factory=time.perf_counter)
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
        payload = {"name": name, "timestamp": time.time(), "attributes": dict(attributes or {})}
        self.events.append(payload)


class TelemetryMetric(BaseModel):
    """Immutable metric point for runtime performance and throughput tracking."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    metric_name: str
    value: float
    unit: str = "ms"
    timestamp: float = Field(default_factory=time.time)
    tags: dict[str, Any] = Field(default_factory=dict)


class HistogramSummary(BaseModel):
    """Immutable aggregated summary statistics and quantiles for a histogram series."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    count: int
    sum: float
    min: float
    max: float
    p50: float
    p95: float
    p99: float
    buckets: dict[str, int] = Field(default_factory=dict)


def parse_traceparent(header: str) -> tuple[str, str] | None:
    """Parse a W3C traceparent header into (trace_id, parent_span_id), or None if invalid."""
    match = TRACEPARENT_RE.match(header.strip().lower())
    if not match:
        return None
    trace_id, parent_span_id = match.group(1), match.group(2)
    if trace_id == "0" * 32 or parent_span_id == "0" * 16:
        return None
    return trace_id, parent_span_id
