"""Cross-platform bounded ALOS validation suite orchestrator.

Runs lightweight static checks with bounded concurrency (max 2 workers) first, then runs
pytest and Behave cleanly in sequence locally so workstation memory/IDE stability is preserved.

Spec: specs/035-parallel-testing-and-qa-matrix/spec.md (FR-005, FR-009)
ADR: ADR-0019
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess  # nosec B404
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class GateResult:
    """Outcome of a single validation gate."""

    index: int
    label: str
    elapsed_s: float
    returncode: int
    stdout: str
    stderr: str


def _run_gate(
    index: int, label: str, cmd: list[str], env: dict[str, str] | None = None
) -> GateResult:
    started = time.perf_counter()
    # Execute fixed command list in repository root without shell invocation.
    proc = subprocess.run(  # noqa: S603  # nosec B603
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    return GateResult(
        index=index,
        label=label,
        elapsed_s=round(time.perf_counter() - started, 2),
        returncode=proc.returncode,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
    )


def _build_static_gates() -> list[tuple[int, str, list[str]]]:
    uv = shutil.which("uv") or "uv"
    py = sys.executable
    gates: list[tuple[int, str, list[str]]] = [
        (1, "uv.lock sync check", [uv, "lock", "--check"]),
        (
            2,
            "Ruff format check",
            [
                py,
                "-m",
                "ruff",
                "format",
                "--check",
                "alos",
                "tests",
                "features",
                "alembic",
                "scripts",
            ],
        ),
        (
            3,
            "Ruff lint check",
            [py, "-m", "ruff", "check", "alos", "tests", "features", "alembic", "scripts"],
        ),
        (4, "Mypy static type check", [py, "-m", "mypy", "alos", "tests", "features", "scripts"]),
        (5, "Bandit security scan", [py, "-m", "bandit", "-r", "alos", "-s", "B101", "-q"]),
        (6, "pyadr ADR sanity check", [uv, "run", "pyadr", "check-adr-repo", "--no-ansi"]),
    ]
    cargo = shutil.which("cargo")
    if cargo is not None:
        manifest = "crates/alos_native/Cargo.toml"
        gates.extend(
            [
                (
                    7,
                    "Rust cargo fmt check",
                    [cargo, "fmt", "--manifest-path", manifest, "--", "--check"],
                ),
                (
                    8,
                    "Rust cargo clippy check",
                    [
                        cargo,
                        "clippy",
                        "--manifest-path",
                        manifest,
                        "--no-default-features",
                        "--",
                        "-D",
                        "warnings",
                    ],
                ),
                (
                    9,
                    "Rust cargo unit & proptest suite",
                    [cargo, "test", "--manifest-path", manifest, "--no-default-features"],
                ),
            ]
        )
    return gates


def _print_gate_results(results: list[GateResult]) -> bool:
    failed = False
    for res in sorted(results, key=lambda r: r.index):
        status = "PASS" if res.returncode == 0 else "FAIL"
        print(f"==> [{status}] {res.index}. {res.label} ({res.elapsed_s:.2f}s)")
        if res.returncode != 0:
            failed = True
            if res.stdout.strip():
                print(res.stdout.rstrip())
            if res.stderr.strip():
                print(res.stderr.rstrip(), file=sys.stderr)
    return not failed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bounded cross-platform ALOS validation suite.")
    parser.add_argument("--skip-live", action="store_true", help="Skip @live GPU/Docker BDD lane")
    parser.add_argument("--require-live", action="store_true", help="Fail if @live is skipped")
    parser.add_argument("--cov-fail-under", type=int, default=90, help="Minimum coverage floor")
    args = parser.parse_args(argv)

    suite_started = time.perf_counter()
    static_gates = _build_static_gates()
    static_workers = 2 if os.environ.get("CI", "").lower() != "true" else 4
    print(f"Running {len(static_gates)} static gates (max_workers={static_workers})...")

    results: list[GateResult] = []
    with ThreadPoolExecutor(max_workers=static_workers) as pool:
        futs = [pool.submit(_run_gate, idx, label, cmd) for idx, label, cmd in static_gates]
        for fut in as_completed(futs):
            results.append(fut.result())

    if not _print_gate_results(results):
        shutil.rmtree(REPO_ROOT / ".pytest_tmp", ignore_errors=True)
        return 1

    pytest_res = _run_gate(
        10,
        f"Pytest bounded-parallel unit/meta/fuzz suite (>={args.cov_fail_under}%)",
        [
            sys.executable,
            "scripts/run_pytest_clean.py",
            "--cov=alos",
            "--cov-report=term-missing",
            f"--cov-fail-under={args.cov_fail_under}",
            "-q",
        ],
    )
    if not _print_gate_results([pytest_res]):
        shutil.rmtree(REPO_ROOT / ".pytest_tmp", ignore_errors=True)
        return 1

    behave_workers = "4" if os.environ.get("CI", "").lower() == "true" else "2"
    mocked_res = _run_gate(
        11,
        "Behave BDD bounded-parallel mocked suite (@mocked)",
        [
            sys.executable,
            "scripts/run_behave_parallel.py",
            "--tags=@mocked",
            "--workers",
            behave_workers,
        ],
    )
    if not _print_gate_results([mocked_res]):
        shutil.rmtree(REPO_ROOT / ".pytest_tmp", ignore_errors=True)
        return 1

    if not args.skip_live:
        live_cmd = [sys.executable, "scripts/run_behave_parallel.py", "--tags=@live"]
        if args.require_live:
            live_cmd.append("--require-live")
        live_res = _run_gate(12, "Behave BDD serialized hardware lane (@live)", live_cmd)
        if not _print_gate_results([live_res]):
            shutil.rmtree(REPO_ROOT / ".pytest_tmp", ignore_errors=True)
            return 1

    shutil.rmtree(REPO_ROOT / ".pytest_tmp", ignore_errors=True)
    elapsed = round(time.perf_counter() - suite_started, 2)
    print(f"\nALL VALIDATION GATES PASSED in {elapsed:.2f}s.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
