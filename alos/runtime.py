"""Portable production runtime layout, single-instance locking, health probes, and bootstrap.

Spec: specs/034-portable-production-runtime/spec.md (FR-001 through FR-005)
Spec: specs/035-parallel-testing-and-qa-matrix/spec.md (FR-001, FR-007, FR-014)
ADRs: ADR-0018, ADR-0019
"""

from __future__ import annotations

import contextlib
import ctypes
import importlib.resources
import json
import os
import shutil
import socket
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import TracebackType
from typing import Any

from sqlalchemy import select, text

from alos.config.settings import ALOSSettings
from alos.db.models import ComputeCapacityLedgerModel, ComputeQueueJobModel
from alos.db.session import DatabaseManager
from alos.swarm.dispatcher import DEFAULT_HOST, Ollama
from alos.swarm.governor import DEFAULT_MODEL_TIERS
from alos.swarm.sensors import WindowsNativeSensor, query_win32_free_commit_mb

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
ERROR_ACCESS_DENIED = 5
STILL_ACTIVE = 259
VAULT_TEMPLATE_FILES = ("USER_PROFILE.md", "PREFERENCES.md", "CORRECTION_LEDGER.md")
DEFAULT_ENV_TEMPLATE = """# ALOS Portable Runtime Configuration
# Override ALOS_QUEUE_DB_URL to switch from local SQLite to PostgreSQL:
# ALOS_QUEUE_DB_URL=postgresql+psycopg://postgres:postgres@localhost:5432/alos
ALOS_MOCK_MODE=false
ALOS_SWARM_OLLAMA=http://127.0.0.1:11434
"""


class DaemonAlreadyRunningError(RuntimeError):
    """Raised when another live ALOS governor daemon holds the runtime lockfile."""


def allocate_free_port(host: str = "127.0.0.1") -> int:
    """Ask the OS kernel for an unused ephemeral TCP port on ``host``."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


@dataclass(frozen=True)
class RuntimePaths:
    """Self-contained directory layout under ``ALOS_HOME`` for portable/container execution."""

    root: Path

    @classmethod
    def resolve(cls, home: Path | str | None = None) -> RuntimePaths:
        """Resolve ``ALOS_HOME`` from explicit path, env vars, or ``~/.alos``."""
        if home is not None:
            return cls(root=Path(home).expanduser().resolve())
        settings = ALOSSettings()
        env_home = settings.alos_home or settings.swarm_home
        target = Path(env_home) if env_home else (Path.home() / ".alos")
        return cls(root=target.expanduser().resolve())

    @property
    def vault_dir(self) -> Path:
        return self.root / "vault"

    @property
    def queue_dir(self) -> Path:
        return self.root / "queue"

    @property
    def logs_dir(self) -> Path:
        return self.root / "logs"

    @property
    def run_dir(self) -> Path:
        return self.root / "run"

    @property
    def env_file(self) -> Path:
        return self.root / "alos.env"

    @property
    def lock_file(self) -> Path:
        return self.run_dir / "governor.lock"

    @property
    def health_file(self) -> Path:
        return self.run_dir / "health.json"

    @property
    def hold_file(self) -> Path:
        return self.run_dir / "queue_hold.json"

    @property
    def results_dir(self) -> Path:
        return self.root / "results"

    @property
    def sqlite_db_path(self) -> Path:
        return self.queue_dir / "compute_queue.db"

    def resolve_db_url(self, explicit_url: str | None = None) -> str:
        """Return explicit DB URL, ``ALOS_QUEUE_DB_URL`` env override, or portable SQLite URL."""
        if explicit_url:
            return explicit_url
        env_url = ALOSSettings().queue_db_url
        if env_url:
            return env_url
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{self.sqlite_db_path.as_posix()}"


def _is_windows_pid_alive(pid: int) -> bool:
    win = getattr(ctypes, "windll", None)
    if win is None:
        return False
    handle = win.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not handle:
        last_err = int(win.kernel32.GetLastError())
        return last_err == ERROR_ACCESS_DENIED
    try:
        exit_code = ctypes.c_ulong(0)
        if not win.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return False
        return int(exit_code.value) == STILL_ACTIVE
    finally:
        win.kernel32.CloseHandle(handle)


def is_pid_alive(pid: int) -> bool:
    """Return True when ``pid`` refers to a currently running OS process."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        return _is_windows_pid_alive(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class SingleInstanceLock:
    """Exclusive PID lockfile preventing split-brain duplicate governor daemons."""

    def __init__(self, lock_path: Path) -> None:
        self.lock_path = lock_path
        self._acquired = False
        self._token = uuid.uuid4().hex

    def _read_holder(self) -> tuple[int, str]:
        for _ in range(3):
            with contextlib.suppress(OSError, ValueError, KeyError):
                data = json.loads(self.lock_path.read_text(encoding="utf-8"))
                return int(data.get("pid", 0)), str(data.get("token", ""))
            time.sleep(0.002)
        return 0, ""

    def _try_atomic_create(self) -> bool:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {
                "pid": os.getpid(),
                "token": self._token,
                "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
        )
        tmp_path = self.lock_path.with_name(
            f".{self.lock_path.name}.{os.getpid()}.{self._token[:8]}.tmp"
        )
        tmp_path.write_text(payload, encoding="utf-8")
        try:
            os.link(str(tmp_path), str(self.lock_path))
            self._acquired = True
            return True
        except FileExistsError:
            return False
        except OSError:
            return self._fallback_excl_create(payload)
        finally:
            with contextlib.suppress(OSError):
                tmp_path.unlink()

    def _fallback_excl_create(self, payload: str) -> bool:
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        try:
            fd = os.open(str(self.lock_path), flags, 0o600)
        except FileExistsError:
            return False
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        self._acquired = True
        return True

    def _reclaim_stale_under_gate(self) -> bool:
        reclaim_gate = self.lock_path.with_name(f".{self.lock_path.name}.reclaim")
        try:
            os.mkdir(str(reclaim_gate))
        except FileExistsError:
            time.sleep(0.015)
            return self._try_atomic_create()
        try:
            holder_pid, _ = self._read_holder()
            if is_pid_alive(holder_pid):
                return False
            with contextlib.suppress(OSError):
                self.lock_path.unlink()
            return self._try_atomic_create()
        finally:
            with contextlib.suppress(OSError):
                os.rmdir(str(reclaim_gate))

    def acquire(self) -> None:
        """Acquire exclusive lock or atomically reclaim stale lock left by a dead process."""
        if self._try_atomic_create():
            return
        holder_pid, _ = self._read_holder()
        if is_pid_alive(holder_pid):
            msg = f"ALOS governor daemon is already running (PID {holder_pid}, {self.lock_path})"
            raise DaemonAlreadyRunningError(msg)
        if self._reclaim_stale_under_gate():
            return
        holder_pid, _ = self._read_holder()
        msg = f"ALOS governor daemon is already running (PID {holder_pid}, {self.lock_path})"
        raise DaemonAlreadyRunningError(msg)

    def release(self) -> None:
        """Remove lockfile only if still owned by this instance's token."""
        if not self._acquired:
            return
        self._acquired = False
        _, current_token = self._read_holder()
        if current_token in ("", self._token):
            with contextlib.suppress(OSError):
                self.lock_path.unlink()

    def __enter__(self) -> SingleInstanceLock:
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.release()


class HealthHeartbeat:
    """Writes atomic ``run/health.json`` snapshots for container healthchecks and monitors."""

    def __init__(self, health_path: Path) -> None:
        self.health_path = health_path

    def write(self, status: str, governor_state: str, active_tier: str | None = None) -> Path:
        """Atomically persist health JSON via per-thread temporary sibling rename."""
        self.health_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "status": status,
            "governor_state": governor_state,
            "active_tier": active_tier,
            "pid": os.getpid(),
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        tmp = self.health_path.with_name(
            f".{self.health_path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
        )
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        try:
            for attempt in range(4):
                try:
                    tmp.replace(self.health_path)
                    break
                except PermissionError:
                    if attempt == 3:
                        raise
                    time.sleep(0.005 * (attempt + 1))
        finally:
            if tmp.exists():
                with contextlib.suppress(OSError):
                    tmp.unlink()
        return self.health_path


def _seed_vault_templates(vault_dir: Path) -> list[str]:
    vault_dir.mkdir(parents=True, exist_ok=True)
    seeded: list[str] = []
    pkg_files = importlib.resources.files("alos.templates.vault")
    for name in VAULT_TEMPLATE_FILES:
        dest = vault_dir / name
        if dest.exists():
            continue
        content = pkg_files.joinpath(name).read_text(encoding="utf-8")
        dest.write_text(content, encoding="utf-8")
        seeded.append(name)
    return seeded


def bootstrap_home(home: Path | str | None = None, db_url: str | None = None) -> dict[str, Any]:
    """Initialize portable ``ALOS_HOME`` directories, vault templates, env file, and DB schema."""
    paths = RuntimePaths.resolve(home)
    for directory in (
        paths.vault_dir,
        paths.queue_dir,
        paths.logs_dir,
        paths.run_dir,
        paths.results_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    seeded = _seed_vault_templates(paths.vault_dir)
    if not paths.env_file.exists():
        paths.env_file.write_text(DEFAULT_ENV_TEMPLATE, encoding="utf-8")
    resolved_db = paths.resolve_db_url(db_url)
    db = DatabaseManager(db_url=resolved_db)
    db.create_all_tables()
    return {
        "status": "bootstrapped",
        "home": str(paths.root),
        "vault_dir": str(paths.vault_dir),
        "db_url": resolved_db,
        "seeded_vault_files": seeded,
        "tables_ready": True,
    }


def _probe_database(db_url: str) -> dict[str, Any]:
    try:
        db = DatabaseManager(db_url=db_url)
        with db.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"ok": True, "url": db_url}
    except Exception as exc:
        return {"ok": False, "url": db_url, "error": str(exc)}


def _probe_ollama(ollama_host: str, mock: bool) -> dict[str, Any]:
    if mock:
        return {
            "ok": True,
            "host": ollama_host,
            "installed_models": [spec.model for spec in DEFAULT_MODEL_TIERS.values()],
            "missing_tier_models": [],
        }
    try:
        tags = Ollama(ollama_host).call("/api/tags", timeout=0.4)
        installed = sorted({str(m.get("name", "")) for m in tags.get("models", [])})
        wanted = {spec.model for spec in DEFAULT_MODEL_TIERS.values()}
        missing = sorted(wanted - set(installed))
        return {
            "ok": True,
            "host": ollama_host,
            "installed_models": installed,
            "missing_tier_models": missing,
        }
    except (OSError, ValueError) as exc:
        return {"ok": False, "host": ollama_host, "error": str(exc), "missing_tier_models": []}


def _probe_home_writable(paths: RuntimePaths) -> dict[str, Any]:
    try:
        paths.run_dir.mkdir(parents=True, exist_ok=True)
        probe = paths.run_dir / f".write_probe_{os.getpid()}_{threading.get_ident()}"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return {"ok": True, "path": str(paths.root)}
    except OSError as exc:
        return {"ok": False, "path": str(paths.root), "error": str(exc)}


def run_doctor(
    home: Path | str | None = None,
    db_url: str | None = None,
    ollama_host: str | None = None,
    require_ollama: bool = False,
    mock: bool = False,
) -> dict[str, Any]:
    """Run production preflight checks across filesystem, DB, vault, GPU, Ollama, and Docker."""
    paths = RuntimePaths.resolve(home)
    resolved_db = paths.resolve_db_url(db_url)
    host = ollama_host or ALOSSettings().swarm_ollama_host or DEFAULT_HOST

    home_check = _probe_home_writable(paths)
    db_check = _probe_database(resolved_db)
    vault_present = (paths.vault_dir / "USER_PROFILE.md").exists() or Path(
        "vault/USER_PROFILE.md"
    ).exists()
    nvml_ok = True if mock else WindowsNativeSensor(ollama_hosts=()).nvml_available
    free_commit = 16384 if mock else query_win32_free_commit_mb()
    ollama_check = _probe_ollama(host, mock=mock)
    docker_ok = True if mock else (shutil.which("docker") is not None)

    healthy = bool(home_check["ok"]) and bool(db_check["ok"])
    if require_ollama and not ollama_check["ok"]:
        healthy = False
    return {
        "healthy": healthy,
        "home": str(paths.root),
        "checks": {
            "home_writable": home_check,
            "database": db_check,
            "vault_seeded": {"ok": vault_present, "vault_dir": str(paths.vault_dir)},
            "gpu_nvml": {"available": nvml_ok},
            "commit_memory": {
                "free_mb": free_commit,
                "low_headroom_warning": free_commit is not None and free_commit < 8192,
            },
            "ollama": ollama_check,
            "docker_cli": {"available": docker_ok},
        },
    }


def query_ledger(db_url: str, limit: int = 10) -> list[dict[str, Any]]:
    """Return the most recent ``limit`` capacity & thermal ledger entries."""
    db = DatabaseManager(db_url=db_url)
    db.create_all_tables()
    with db.get_session() as session:
        stmt = (
            select(ComputeCapacityLedgerModel)
            .order_by(ComputeCapacityLedgerModel.id.desc())
            .limit(max(1, limit))
        )
        rows = list(session.scalars(stmt))
        return [
            {
                "id": r.id,
                "recorded_at": r.recorded_at.isoformat() if r.recorded_at else None,
                "governor_state": r.governor_state,
                "active_tier": r.active_tier,
                "gpu_temp_c": r.gpu_temp_c,
                "used_vram_mb": r.used_vram_mb,
                "managed_vram_mb": r.managed_vram_mb,
                "jobs_waiting": r.jobs_waiting,
                "jobs_done_delta": r.jobs_done_delta,
                "jobs_preempted_delta": r.jobs_preempted_delta,
                "oldest_wait_seconds": r.oldest_wait_seconds,
            }
            for r in rows
        ]


def query_jobs(db_url: str, state: str | None = None, limit: int = 25) -> list[dict[str, Any]]:
    """Return queue jobs ordered by update timestamp, optionally filtered by ``state``."""
    db = DatabaseManager(db_url=db_url)
    db.create_all_tables()
    with db.get_session() as session:
        stmt = select(ComputeQueueJobModel).order_by(ComputeQueueJobModel.updated_at.desc())
        if state:
            stmt = stmt.where(ComputeQueueJobModel.state == state)
        rows = list(session.scalars(stmt.limit(max(1, limit))))
        return [
            {
                "job_id": r.job_id,
                "repo_slug": r.repo_slug,
                "workflow_type": r.workflow_type,
                "model_tier": r.model_tier,
                "priority": r.priority,
                "requires_merge": r.requires_merge,
                "state": r.state,
                "attempts": r.attempts,
                "last_error": r.last_error,
                "result": r.result_json,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ]


@dataclass(frozen=True)
class HoldStatus:
    """Evaluated outcome of the persistent queue staging hold latch (Spec 037)."""

    held: bool
    outcome: str
    mode: str | None
    reason: str
    min_idle_s: float = 0.0


class QueueHoldLatch:
    """File-backed hold latch preventing GPU warm-up while the user is actively at the desk."""

    def __init__(self, hold_path: Path) -> None:
        self.hold_path = hold_path

    def _write_state(self, mode: str, min_idle_s: float, reason: str) -> dict[str, Any]:
        self.hold_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "mode": mode,
            "min_idle_s": float(min_idle_s),
            "reason": reason,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        self.hold_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    def engage_manual(self, reason: str = "manual pause") -> dict[str, Any]:
        """Hold queue execution unconditionally until ``clear()`` / ``resume`` is called."""
        return self._write_state("manual", 0.0, reason)

    def engage_idle_gate(
        self, min_idle_s: float = 300.0, reason: str = "staged while using machine"
    ) -> dict[str, Any]:
        """Hold queue execution until uninterrupted user idle reaches ``min_idle_s``."""
        return self._write_state("idle_gate", max(1.0, float(min_idle_s)), reason)

    def clear(self) -> bool:
        """Remove active hold latch and return True when a latch was cleared."""
        if not self.hold_path.exists():
            return False
        with contextlib.suppress(OSError):
            self.hold_path.unlink()
        return True

    def read(self) -> dict[str, Any] | None:
        """Return persisted hold latch dictionary or None when unlatched."""
        if not self.hold_path.exists():
            return None
        with contextlib.suppress(OSError, ValueError):
            loaded: dict[str, Any] = json.loads(self.hold_path.read_text(encoding="utf-8"))
            return loaded
        return None

    def evaluate(
        self,
        user_idle_seconds: float,
        d3d_fullscreen: bool = False,
        blocked_process: str | None = None,
    ) -> HoldStatus:
        """Check whether execution must stay held or auto-arm after hands-off idle expiry."""
        data = self.read()
        if data is None:
            return HoldStatus(False, "open", None, "")
        mode, reason = str(data.get("mode", "manual")), str(data.get("reason", "queue held"))
        min_idle = float(data.get("min_idle_s", 0.0))
        if mode == "manual":
            return HoldStatus(True, "held", "manual", reason)
        if not d3d_fullscreen and blocked_process is None and user_idle_seconds >= min_idle:
            self.clear()
            return HoldStatus(False, "armed_from_idle", None, "idle threshold satisfied", min_idle)
        return HoldStatus(True, "held_user_active", "idle_gate", reason, min_idle)


def review_jobs(
    db_url: str,
    job_id: str | None = None,
    repo_slug: str | None = None,
    action: str = "approve",
) -> dict[str, Any]:
    """Transition ``review_pending`` jobs to ``succeeded``, ``queued``, or ``escalated``."""
    state_map = {"approve": "succeeded", "requeue": "queued", "reject": "escalated"}
    target_state = state_map.get(action)
    if target_state is None:
        raise ValueError(f"unsupported review action {action!r}")
    now = datetime.now(timezone.utc)
    db = DatabaseManager(db_url=db_url)
    db.create_all_tables()
    updated_ids: list[str] = []
    with db.get_session() as session:
        stmt = select(ComputeQueueJobModel).where(ComputeQueueJobModel.state == "review_pending")
        if job_id:
            stmt = stmt.where(ComputeQueueJobModel.job_id == job_id)
        if repo_slug:
            stmt = stmt.where(ComputeQueueJobModel.repo_slug == repo_slug)
        for row in session.scalars(stmt):
            row.state = target_state
            if action == "requeue":
                row.attempts = 0
            row.updated_at = now
            updated_ids.append(row.job_id)
        session.flush()
    return {"updated": len(updated_ids), "target_state": target_state, "job_ids": updated_ids}
