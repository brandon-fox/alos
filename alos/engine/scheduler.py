from typing import Any

# Third-party library apscheduler lacks PEP 561 py.typed marker or type stubs
from apscheduler.schedulers.background import (  # type: ignore[import-untyped]
    BackgroundScheduler as APSchedulerEngine,
)

from alos.core.graph import ALOSStateGraph


class BackgroundScheduler:
    """Trigger & Scheduler Engine running morning sweeps & heartbeat events via APScheduler."""

    def __init__(self, vault_dir: str, graph: ALOSStateGraph | None = None):
        self.graph = graph if graph is not None else ALOSStateGraph(vault_dir=vault_dir)
        self._scheduler = APSchedulerEngine()

    def start(self) -> None:
        """Start the background APScheduler loop."""
        if not self._scheduler.running:
            self._scheduler.start()

    def shutdown(self) -> None:
        """Shutdown the background APScheduler loop."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    def run_morning_sweep(self) -> dict[str, Any]:
        """Execute morning routine sweep: check agenda, query tasks, and organize schedule."""
        return self.graph.run("Query agenda and schedule morning tasks")
