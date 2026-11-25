"""Ring 3 outbound boundary adapter wrapping stdlib-only alos.swarm execution engines."""

from __future__ import annotations

from typing import Any

from alos.db.session import DatabaseManager
from alos.swarm import dispatcher, governor, queue, sandbox


class SwarmBoundaryAdapter:
    """Typed boundary delegating dynamically to preserve swarm test monkeypatches."""

    def probe_gpu_stats(self) -> tuple[int, int, int] | None:
        """Query GPU utilization and VRAM via dispatcher.gpu_stats."""
        return dispatcher.gpu_stats()

    def list_running_processes(self) -> str:
        """Query running host processes via dispatcher.running_processes."""
        return dispatcher.running_processes()

    def gate_check(
        self, client: dispatcher.Ollama, processes: list[str], vram_mb: int
    ) -> str | None:
        """Evaluate host execution gate via dispatcher.gate."""
        return dispatcher.gate(client, processes, vram_mb)

    def execute_run(self, run: dispatcher.Run, *, force: bool = False) -> tuple[str, str]:
        """Execute a swarm dispatcher Run via dispatcher.execute."""
        return dispatcher.execute(run, force=force)

    def run_container(self, argv: list[str], name: str, timeout_s: float) -> tuple[int | None, str]:
        """Execute an isolated container command via sandbox.run_container."""
        return sandbox.run_container(argv, name, timeout_s)

    def check_sandbox_job(self, job: dict[str, Any], limits: sandbox.Limits) -> dict[str, Any]:
        """Execute a sandbox verification job via sandbox.check_job."""
        return sandbox.check_job(job, limits)

    def create_governor(
        self,
        sensor: Any,
        *,
        spinner: governor.ModelSpinner | None = None,
        config: governor.HysteresisConfig | None = None,
    ) -> governor.HostGovernor:
        """Instantiate a configured HostGovernor wrapping GPU/thermal hysteresis."""
        return governor.HostGovernor(
            sensor=sensor,
            spinner=spinner or governor.ModelSpinner(),
            config=config or governor.HysteresisConfig(),
        )

    def open_sticky_queue(
        self, db_url: str, *, config: queue.QueueConfig | None = None
    ) -> queue.StickyEpochQueue:
        """Open a WAL-mode StickyEpochQueue for the configured SQLite/Postgres URL."""
        db = DatabaseManager(db_url=db_url)
        db.create_all_tables()
        return queue.StickyEpochQueue(db=db, config=config)
