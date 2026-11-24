"""Runtime Health Monitoring, SLO Alerting & Local-First HTTP Observability Server.

Spec: specs/031-runtime-observability-monitoring/spec.md (FR-005, FR-006)
Constitution: Article II (Local-First Loopback Privacy), Article VI (Self-Healing Non-Intrusiveness)
"""

from __future__ import annotations

import gc
import json
import os
import platform
import sys
import threading
import time
import tracemalloc
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from alos.core.config import ALOSConfig
from alos.logs.telemetry import TelemetryTracer, global_tracer
from alos.native import HAS_NATIVE_EXTENSION

HealthState = Literal["HEALTHY", "DEGRADED", "UNHEALTHY"]


class ComponentHealth(BaseModel):
    """Readiness state for a single runtime subsystem."""

    name: str
    status: HealthState
    detail: str


class SLOAlert(BaseModel):
    """Alert emitted when an active runtime metric breaches a configured SLO threshold."""

    severity: Literal["WARNING", "CRITICAL"]
    metric: str
    observed: float
    threshold: float
    message: str


class RuntimeStats(BaseModel):
    """Point-in-time process and Python interpreter resource telemetry."""

    pid: int
    python_version: str
    platform: str
    uptime_seconds: float
    active_threads: int
    memory_rss_bytes: int
    python_heap_bytes: int
    gc_collections: int
    native_extension_loaded: bool


class HealthReport(BaseModel):
    """Aggregate readiness report combining runtime telemetry, probes, and SLO alerts."""

    status: HealthState
    timestamp: str
    runtime: RuntimeStats
    components: list[ComponentHealth]
    alerts: list[SLOAlert]


def _read_rss_bytes(heap_fallback: int) -> int:
    statm = Path("/proc/self/statm")
    if statm.exists():
        try:
            pages = int(statm.read_text(encoding="utf-8").split()[1])
            return pages * 4096
        except (OSError, ValueError, IndexError):
            return heap_fallback
    return heap_fallback


class RuntimeMonitor:
    """Monitors process resources, subsystem readiness, and runtime SLO compliance."""

    def __init__(
        self,
        config: ALOSConfig | None = None,
        tracer: TelemetryTracer | None = None,
        vault_dir: str | None = None,
        log_dir: str | None = None,
    ) -> None:
        self.config = config or ALOSConfig()
        self.tracer = tracer or global_tracer
        self.vault_dir = vault_dir or self.config.vault_dir
        self.log_dir = log_dir or os.path.join(os.getcwd(), "logs")
        self._started = time.monotonic()

    def collect_runtime_stats(self) -> RuntimeStats:
        """Collect process/interpreter stats and synchronize runtime gauges."""
        uptime = round(time.monotonic() - self._started, 3)
        threads = threading.active_count()
        heap = tracemalloc.get_traced_memory()[0] if tracemalloc.is_tracing() else 0
        rss = _read_rss_bytes(heap)
        gc_total = sum(int(gen.get("collections", 0)) for gen in gc.get_stats())
        self.tracer.set_gauge("alos_process_uptime_seconds", uptime)
        self.tracer.set_gauge("alos_runtime_active_threads", float(threads))
        self.tracer.set_gauge("alos_process_memory_bytes", float(rss))
        return RuntimeStats(
            pid=os.getpid(),
            python_version=sys.version.split()[0],
            platform=platform.system(),
            uptime_seconds=uptime,
            active_threads=threads,
            memory_rss_bytes=rss,
            python_heap_bytes=heap,
            gc_collections=gc_total,
            native_extension_loaded=HAS_NATIVE_EXTENSION,
        )

    def _probe_components(self) -> list[ComponentHealth]:
        vault_ok = os.path.isdir(self.vault_dir)
        journal_ok = True
        try:
            os.makedirs(self.log_dir, exist_ok=True)
            journal_ok = os.access(self.log_dir, os.W_OK)
        except OSError:
            journal_ok = False
        return [
            ComponentHealth(name="liveness", status="HEALTHY", detail="Process responsive"),
            ComponentHealth(
                name="vault",
                status="HEALTHY" if vault_ok else "DEGRADED",
                detail=self.vault_dir,
            ),
            ComponentHealth(
                name="audit_journals",
                status="HEALTHY" if journal_ok else "UNHEALTHY",
                detail=self.log_dir,
            ),
            ComponentHealth(
                name="native_bridge",
                status="HEALTHY",
                detail="alos_native" if HAS_NATIVE_EXTENSION else "python_fallback",
            ),
        ]

    def evaluate_slos(self) -> list[SLOAlert]:
        """Check p95 latency and run failure rate against configured SLO thresholds."""
        alerts: list[SLOAlert] = []
        slo_ms = self.config.latency_slo_ms
        for key, summary in self.tracer.get_all_histograms().items():
            if "duration_ms" in key and summary.p95 > slo_ms:
                alerts.append(
                    SLOAlert(
                        severity="WARNING",
                        metric=key,
                        observed=summary.p95,
                        threshold=slo_ms,
                        message=f"p95 latency {summary.p95}ms exceeds SLO {slo_ms}ms",
                    )
                )
        ok = self.tracer.get_counter("alos_agent_runs_total", {"status": "SUCCESS"})
        failed = self.tracer.get_counter("alos_agent_runs_total", {"status": "FAILED"})
        total = ok + failed
        if total > 0 and (failed / total) > self.config.error_rate_threshold:
            rate = round(failed / total, 3)
            alerts.append(
                SLOAlert(
                    severity="CRITICAL",
                    metric="alos_agent_runs_error_rate",
                    observed=rate,
                    threshold=self.config.error_rate_threshold,
                    message=f"Error rate {rate} exceeds {self.config.error_rate_threshold}",
                )
            )
        return alerts

    def check_liveness(self) -> dict[str, Any]:
        """Return lightweight liveness payload for /healthz probes."""
        return {
            "status": "UP",
            "pid": os.getpid(),
            "uptime_seconds": round(time.monotonic() - self._started, 3),
        }

    def check_health(self) -> HealthReport:
        """Execute full readiness probes, runtime stats collection, and SLO evaluation."""
        stats = self.collect_runtime_stats()
        components = self._probe_components()
        alerts = self.evaluate_slos()
        comp_states = {c.status for c in components}
        crit = any(a.severity == "CRITICAL" for a in alerts)
        if "UNHEALTHY" in comp_states or crit:
            overall: HealthState = "UNHEALTHY"
        elif "DEGRADED" in comp_states or alerts:
            overall = "DEGRADED"
        else:
            overall = "HEALTHY"
        return HealthReport(
            status=overall,
            timestamp=datetime.now(timezone.utc).isoformat(),
            runtime=stats,
            components=components,
            alerts=alerts,
        )


class ObservabilityServer:
    """Loopback-bound HTTP server exposing /healthz, /readyz, /metrics, and /traces."""

    def __init__(
        self,
        monitor: RuntimeMonitor | None = None,
        tracer: TelemetryTracer | None = None,
        host: str = "127.0.0.1",
        port: int = 9464,
    ) -> None:
        self.tracer = tracer or global_tracer
        self.monitor = monitor or RuntimeMonitor(tracer=self.tracer)
        self.host = host
        self.port = port
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def _dispatch(self, path: str) -> tuple[int, str, bytes]:
        clean = path.split("?", 1)[0]
        if clean == "/healthz":
            body = json.dumps(self.monitor.check_liveness()).encode("utf-8")
            return 200, "application/json", body
        if clean == "/readyz":
            report = self.monitor.check_health()
            code = 503 if report.status == "UNHEALTHY" else 200
            return code, "application/json", report.model_dump_json().encode("utf-8")
        if clean == "/metrics":
            self.monitor.collect_runtime_stats()
            text = self.tracer.render_prometheus().encode("utf-8")
            return 200, "text/plain; version=0.0.4; charset=utf-8", text
        if clean == "/traces":
            spans = [s.model_dump() for s in self.tracer.get_spans(limit=100)]
            return 200, "application/json", json.dumps(spans).encode("utf-8")
        return 404, "application/json", b'{"error":"not_found"}'

    def start(self) -> tuple[str, int]:
        """Start background HTTP server thread and return bound (host, port)."""
        outer = self

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                code, content_type, body = outer._dispatch(self.path)
                self.send_response(code)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: Any) -> None:
                return

        self._httpd = ThreadingHTTPServer((self.host, self.port), _Handler)
        bound = self._httpd.server_address
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return str(bound[0]), int(bound[1])

    def stop(self) -> None:
        """Stop background HTTP server and release socket."""
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
