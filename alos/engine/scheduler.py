from typing import Any

from alos.core.graph import ALOSStateGraph


class BackgroundScheduler:
    """Trigger & Scheduler Engine running morning routine sweeps and cron heartbeat events."""

    def __init__(self, vault_dir: str):
        self.graph = ALOSStateGraph(vault_dir=vault_dir)

    def run_morning_sweep(self) -> dict[str, Any]:
        """Execute morning routine sweep: check agenda, query tasks, and organize schedule."""
        return self.graph.run("Query agenda and schedule morning tasks")
