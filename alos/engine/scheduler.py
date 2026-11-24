"""Background scheduler wrapper using APScheduler for ALOS routines."""

from typing import Any

# Third-party library apscheduler lacks PEP 561 py.typed marker or type stubs
from apscheduler.schedulers.background import (  # type: ignore[import-untyped]
    BackgroundScheduler as APSchedulerEngine,
)

from alos.core.graph import ALOSStateGraph
from alos.core.protocols import TelemetryProtocol
from alos.logs.telemetry import global_tracer


class BackgroundScheduler:
    """Trigger & Scheduler Engine running morning sweeps & heartbeat events via APScheduler."""

    def __init__(
        self,
        vault_dir: str,
        graph: ALOSStateGraph | None = None,
        tracer: TelemetryProtocol | None = None,
    ) -> None:
        self.tracer: TelemetryProtocol = tracer if tracer is not None else global_tracer
        self.graph = (
            graph if graph is not None else ALOSStateGraph(vault_dir=vault_dir, tracer=self.tracer)
        )
        self._scheduler = APSchedulerEngine()

    def start(self) -> None:
        """Start the background APScheduler loop and update running gauge."""
        if not self._scheduler.running:
            self._scheduler.start()
        self.tracer.set_gauge("alos_scheduler_running", 1.0)

    def shutdown(self) -> None:
        """Shutdown the background APScheduler loop and clear running gauge."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
        self.tracer.set_gauge("alos_scheduler_running", 0.0)

    def run_morning_sweep(self) -> dict[str, Any]:
        """Execute morning routine sweep with telemetry span and sweep counter."""
        with self.tracer.span("scheduler.morning_sweep"):
            res = self.graph.run("Query agenda and schedule morning tasks")
        self.tracer.inc_counter(
            "alos_scheduler_sweeps_total",
            labels={"status": str(res.get("status", "SUCCESS"))},
        )
        return res
