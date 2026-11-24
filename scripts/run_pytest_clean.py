"""Execute pytest in parallel with isolated per-invocation temp & coverage directories.

Uses commit-charge-aware worker sizing on Windows and ``--dist loadfile`` so heavy framework
imports (e.g. CrewAI) stay isolated to the single worker executing that module.

Spec: specs/035-parallel-testing-and-qa-matrix/spec.md (FR-001, FR-002)
"""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess  # nosec B404
import sys
import tempfile
from pathlib import Path

import pytest


def _win32_free_commit_mb() -> int | None:
    if sys.platform != "win32":
        return None
    win = getattr(ctypes, "windll", None)
    if win is None:
        return None

    class _MemoryStatusEx(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    stat = _MemoryStatusEx()
    stat.dwLength = ctypes.sizeof(_MemoryStatusEx)
    if not win.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
        return None
    return int(stat.ullAvailPageFile // (1024 * 1024))


def _default_worker_count() -> int:
    env_override = os.environ.get("ALOS_PYTEST_WORKERS")
    if env_override:
        return max(1, int(env_override))
    cpus = os.cpu_count() or 2
    in_ci = os.environ.get("CI", "").lower() == "true"
    if sys.platform == "win32":
        free_mb = _win32_free_commit_mb()
        if free_mb is not None and free_mb < 3072:
            return 1
        return min(cpus, 2 if not in_ci else 4)
    return min(cpus, 4 if in_ci else 2)


def _has_explicit_xdist_flag(args: list[str]) -> bool:
    for idx, arg in enumerate(args):
        if arg in ("-n", "--numprocesses") or arg.startswith(("-n=", "--numprocesses=")):
            return True
        if arg.startswith("-n") and len(arg) > 2 and (arg[2:].isdigit() or arg[2:] == "auto"):
            return True
        if arg == "-p" and idx + 1 < len(args) and "no:xdist" in args[idx + 1]:
            return True
    return False


def _combine_coverage_if_present(cov_base: Path, keep_at_repo: bool) -> None:
    shards = list(cov_base.parent.glob(f"{cov_base.name}*"))
    if not shards:
        return
    env = dict(os.environ, COVERAGE_FILE=str(cov_base))
    if len(shards) > 1 or not cov_base.exists():
        # Combine parallel worker coverage shards using current Python interpreter without shell.
        subprocess.run(  # nosec B603
            [sys.executable, "-m", "coverage", "combine"],
            env=env,
            capture_output=True,
            check=False,
        )
    if keep_at_repo and cov_base.exists():
        shutil.copy2(cov_base, Path.cwd() / ".coverage")


def main(argv: list[str] | None = None) -> int:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    keep_cov = "--keep-coverage" in raw_args or os.environ.get("ALOS_KEEP_COVERAGE") == "1"
    filtered_args = [a for a in raw_args if a != "--keep-coverage"]

    root = Path(tempfile.mkdtemp(prefix="alos_pytest_"))
    cov_file = root / ".coverage"
    prev_cov = os.environ.get("COVERAGE_FILE")
    os.environ["COVERAGE_FILE"] = str(cov_file)

    pytest_args = [f"--basetemp={root / 'run'}"]
    if not _has_explicit_xdist_flag(filtered_args):
        workers = _default_worker_count()
        pytest_args.extend(["-n", str(workers), "--dist", "loadfile"])
    pytest_args.extend(filtered_args)

    try:
        code = int(pytest.main(pytest_args))
        _combine_coverage_if_present(cov_file, keep_at_repo=keep_cov)
        return code
    finally:
        if prev_cov is None:
            os.environ.pop("COVERAGE_FILE", None)
        else:
            os.environ["COVERAGE_FILE"] = prev_cov
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
