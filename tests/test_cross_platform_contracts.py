"""Cross-OS contract & parity verification across Windows (win32/nt) and Linux (POSIX).

Executes both native host OS checks AND mocked cross-OS contract tests so Win32 and POSIX
branches in runtime.py, sensors.py, governor.py, and dispatcher.py are verified on every OS.

Spec: specs/035-parallel-testing-and-qa-matrix/spec.md (FR-014)
ADR: ADR-0020
"""

from __future__ import annotations

import ctypes
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from alos import runtime
from alos.swarm import dispatcher, governor, sensors

pytestmark = [pytest.mark.platform_agnostic, pytest.mark.source]


def test_is_pid_alive_posix_and_windows_contracts(monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-014: Verify POSIX EPERM/ESRCH and Win32 ERROR_ACCESS_DENIED/STILL_ACTIVE contracts."""
    assert runtime.is_pid_alive(0) is False
    assert runtime.is_pid_alive(-10) is False
    assert runtime.is_pid_alive(os.getpid()) is True

    # 1. Simulate POSIX branches on any OS
    monkeypatch.setattr(runtime.sys, "platform", "linux")
    monkeypatch.setattr(runtime.os, "kill", lambda _pid, _sig: None)
    assert runtime.is_pid_alive(4242) is True

    def raise_perm(_pid: int, _sig: int) -> None:
        raise PermissionError("owned by root")

    monkeypatch.setattr(runtime.os, "kill", raise_perm)
    assert runtime.is_pid_alive(1) is True

    def raise_missing(_pid: int, _sig: int) -> None:
        raise ProcessLookupError("no such pid")

    monkeypatch.setattr(runtime.os, "kill", raise_missing)
    assert runtime.is_pid_alive(99999) is False

    # 2. Simulate Win32 OpenProcess branches (ERROR_ACCESS_DENIED=5 vs dead vs STILL_ACTIVE=259)
    monkeypatch.setattr(runtime.sys, "platform", "win32")

    class _FakeKernel32:
        def __init__(
            self, handle: int, last_err: int, exit_code: int, ok_exit: bool = True
        ) -> None:
            self.handle = handle
            self.last_err = last_err
            self.exit_code = exit_code
            self.ok_exit = ok_exit
            self.closed = False

        def OpenProcess(self, _access: int, _inherit: bool, _pid: int) -> int:
            return self.handle

        def GetLastError(self) -> int:
            return self.last_err

        def GetExitCodeProcess(self, _handle: int, out_ptr: Any) -> int:
            if not self.ok_exit:
                return 0
            out_ptr._obj.value = self.exit_code
            return 1

        def CloseHandle(self, _handle: int) -> int:
            self.closed = True
            return 1

    # Access denied (protected system process) -> alive True
    monkeypatch.setattr(
        runtime.ctypes, "windll", SimpleNamespace(kernel32=_FakeKernel32(0, 5, 0)), raising=False
    )
    assert runtime.is_pid_alive(4) is True

    # Invalid parameter (dead PID) -> alive False
    monkeypatch.setattr(
        runtime.ctypes, "windll", SimpleNamespace(kernel32=_FakeKernel32(0, 87, 0)), raising=False
    )
    assert runtime.is_pid_alive(88888) is False

    # Active handle returning STILL_ACTIVE (259) -> alive True & handle closed
    k_alive = _FakeKernel32(101, 0, runtime.STILL_ACTIVE)
    monkeypatch.setattr(runtime.ctypes, "windll", SimpleNamespace(kernel32=k_alive), raising=False)
    assert runtime.is_pid_alive(1234) is True
    assert k_alive.closed is True

    # Exited process returning exit code 0 -> alive False
    k_dead = _FakeKernel32(102, 0, 0)
    monkeypatch.setattr(runtime.ctypes, "windll", SimpleNamespace(kernel32=k_dead), raising=False)
    assert runtime.is_pid_alive(1234) is False

    # Missing windll attribute on Win32 -> alive False
    monkeypatch.setattr(runtime.ctypes, "windll", None, raising=False)
    assert runtime.is_pid_alive(1234) is False


def test_kill_process_tree_posix_and_nt_contracts(monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-014: Verify POSIX killpg + SIGKILL escalation and Windows taskkill /T /F."""
    # Simulate POSIX session leader killpg + SIGKILL escalation; mock before probing pid=0
    # so mutated pid<=0 bounds never signal process group 0 on POSIX runners.
    signals_sent: list[tuple[str, int, int]] = []
    monkeypatch.setattr(governor.os, "name", "posix")
    monkeypatch.setattr(governor.os, "getpgid", lambda pid: pid, raising=False)
    monkeypatch.setattr(
        governor.os,
        "killpg",
        lambda pgid, sig: signals_sent.append(("killpg", pgid, sig)),
        raising=False,
    )
    monkeypatch.setattr(
        governor.os,
        "kill",
        lambda pid, sig: signals_sent.append(("kill", pid, sig)),
    )
    monkeypatch.setattr(governor.time, "sleep", lambda _s: None)
    assert governor.kill_process_tree(0) is False
    assert signals_sent == []
    assert governor.kill_process_tree(555) is True
    assert ("killpg", 555, 15) in signals_sent
    assert ("kill", 555, 9) in signals_sent

    # Simulate POSIX ProcessLookupError on every signal attempt -> False
    def _raise_lookup(*_args: int) -> int:
        raise ProcessLookupError("no such process")

    monkeypatch.setattr(governor.os, "getpgid", _raise_lookup, raising=False)
    monkeypatch.setattr(governor.os, "killpg", _raise_lookup, raising=False)
    monkeypatch.setattr(governor.os, "kill", _raise_lookup)
    assert governor.kill_process_tree(555) is False

    # Verify throttle recovery idle-dwell boundary (kills active_desk_idle_s mutant)
    cfg = governor.HysteresisConfig()
    assert (
        governor.has_throttle_recovered(
            sensors.TelemetrySnapshot(
                gpu_temp_c=40.0,
                cpu_temp_c=40.0,
                user_idle_seconds=cfg.active_desk_idle_s - 1.0,
            ),
            cfg,
        )
        is False
    )
    assert (
        governor.has_throttle_recovered(
            sensors.TelemetrySnapshot(
                gpu_temp_c=40.0,
                cpu_temp_c=40.0,
                user_idle_seconds=cfg.active_desk_idle_s,
            ),
            cfg,
        )
        is True
    )

    # Simulate Windows taskkill /T /F
    monkeypatch.setattr(governor.os, "name", "nt")
    monkeypatch.setattr(
        governor.subprocess,
        "run",
        lambda cmd, **_kw: subprocess.CompletedProcess(cmd, 0, b"", b""),
    )
    assert governor.kill_process_tree(777) is True


def test_sensors_linux_meminfo_and_mocked_nvml_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-014: Verify Linux /proc/meminfo parsing, non-win32 defaults, and NvmlProbe WDDM filter."""
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemTotal: 32768000 kB\nMemAvailable: 12582912 kB\n", encoding="utf-8")

    monkeypatch.setattr(sensors.sys, "platform", "linux")
    assert sensors.query_win32_free_commit_mb(meminfo) == 12288
    assert sensors.query_win32_free_commit_mb(tmp_path / "missing_meminfo") is None
    assert sensors.query_win32_idle_seconds() == 3600.0
    assert sensors.query_win32_d3d_fullscreen() is False

    # Mock NvmlProbe C library calls including WDDM ~2^64-1 sentinel filtering
    class _FakeNvmlLib:
        def nvmlInit_v2(self) -> int:
            return 0

        def nvmlDeviceGetHandleByIndex_v2(self, _idx: Any, handle_ptr: Any) -> int:
            handle_ptr._obj.value = 0xDEAD
            return 0

        def nvmlDeviceGetTemperature(self, _h: Any, _sensor: Any, out: Any) -> int:
            out._obj.value = 61
            return 0

        def nvmlDeviceGetFieldValues(self, _h: Any, _n: Any, fv_ptr: Any) -> int:
            fv_ptr._obj.nvmlReturn = 0
            fv_ptr._obj.value_ui = 74
            return 0

        def nvmlDeviceGetUtilizationRates(self, _h: Any, u_ptr: Any) -> int:
            u_ptr._obj.gpu = 88
            return 0

        def nvmlDeviceGetMemoryInfo(self, _h: Any, m_ptr: Any) -> int:
            m_ptr._obj.used = 4096 * sensors.BYTES_PER_MIB
            m_ptr._obj.total = 16384 * sensors.BYTES_PER_MIB
            return 0

        def nvmlDeviceGetComputeRunningProcesses_v3(self, _h: Any, count_ptr: Any, buf: Any) -> int:
            count_ptr._obj.value = 2
            buf[0].pid = 1001
            buf[0].usedGpuMemory = 2048 * sensors.BYTES_PER_MIB
            buf[1].pid = 1002
            buf[1].usedGpuMemory = (1 << 64) - 1  # Windows WDDM sentinel -> mapped to 0 MiB
            return 0

    monkeypatch.setattr(sensors, "_load_nvml_library", _FakeNvmlLib)
    probe = sensors.NvmlProbe(0)
    assert probe.available is True
    assert probe.read_gpu_temp() == 61.0
    assert probe.read_vram_temp() == 74.0
    assert probe.read_utilization_and_memory() == (88, 4096, 16384)
    assert probe.read_compute_processes() == {1001: 2048, 1002: 0}
    assert ctypes.sizeof(ctypes.c_void_p) >= 4


def test_dispatcher_running_processes_and_stop_server_parity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-014: Verify dispatcher.running_processes quotes POSIX ps output identically to CSV."""
    monkeypatch.setattr(dispatcher.os, "name", "posix")
    monkeypatch.setattr(
        dispatcher.subprocess,
        "run",
        lambda cmd, **_kw: subprocess.CompletedProcess(cmd, 0, "systemd\nSteam\n", ""),
    )
    listing = dispatcher.running_processes()
    assert '"steam"' in listing

    # POSIX stop_server terminates cleanly
    terminated = {"called": False, "killed": False}

    class _DummyProc:
        pid = 3210

        def terminate(self) -> None:
            terminated["called"] = True

        def wait(self, timeout: float = 15) -> int:
            raise subprocess.TimeoutExpired(cmd="ollama", timeout=timeout)

        def kill(self) -> None:
            terminated["killed"] = True

    dispatcher.stop_server(_DummyProc())  # type: ignore[arg-type]
    assert terminated["called"] is True and terminated["killed"] is True


def _load_run_python_mutants() -> Any:
    """Dynamically load scripts/run_python_mutants.py to keep MyPy module paths disjoint."""
    script = Path(__file__).resolve().parent.parent / "scripts" / "run_python_mutants.py"
    spec = importlib.util.spec_from_file_location("run_python_mutants", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["run_python_mutants"] = module
    spec.loader.exec_module(module)
    return module


def test_mutant_runner_isolates_posix_sessions(monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-013: Isolate POSIX mutant subprocesses into a new session to avoid runner SIGTERM."""
    run_python_mutants = _load_run_python_mutants()

    seen: list[tuple[str, bool]] = []
    cand = run_python_mutants.MutantCandidate(
        rel_file="alos/domain/services/lifecycle_fsm.py",
        lineno=1,
        description="noop",
        mutated_source=(
            run_python_mutants.REPO_ROOT / "alos/domain/services/lifecycle_fsm.py"
        ).read_text(encoding="utf-8"),
        test_files=("tests/test_domain_policies.py",),
    )

    def _fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen.append((run_python_mutants.sys.platform, bool(kwargs.get("start_new_session"))))
        return subprocess.CompletedProcess(cmd, 1, "", "")

    monkeypatch.setattr(run_python_mutants.subprocess, "run", _fake_run)
    for platform_name in ("linux", "win32"):
        monkeypatch.setattr(run_python_mutants.sys, "platform", platform_name)
        outcome = run_python_mutants._evaluate_mutant(cand, timeout_s=5.0)
        assert outcome.status == "killed"
    assert seen == [("linux", True), ("win32", False)]
