"""Cross-platform zero-fork AST mutation testing runner for Windows and Linux.

Generates syntax-valid operator and boolean mutants for high-risk ALOS domain modules
inside isolated temporary package overlays and executes mapped pytest suites concurrently.

Spec: specs/035-parallel-testing-and-qa-matrix/spec.md (FR-013, NFR-006)
ADR: ADR-0020
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import shutil
import subprocess  # nosec B404
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_TARGETS: dict[str, list[str]] = {
    "alos/core/evaluator.py": [
        "tests/test_coverage_fortification.py",
        "tests/test_sdd_bdd_features.py",
        "tests/step_defs/test_03_safety_matrix.py",
        "tests/test_expanded_coverage.py",
    ],
    "alos/swarm/governor.py": [
        "tests/test_swarm_governor.py",
        "tests/test_cross_platform_contracts.py",
    ],
    "alos/swarm/queue.py": [
        "tests/test_swarm_queue.py",
        "tests/test_contention_stress.py",
        "tests/test_portable_runtime.py",
        "tests/test_expanded_coverage.py",
    ],
    "alos/swarm/sandbox.py": [
        "tests/test_swarm_sandbox.py",
        "tests/test_expanded_coverage.py",
    ],
    "alos/runtime.py": [
        "tests/test_portable_runtime.py",
        "tests/test_cross_platform_contracts.py",
    ],
}

COMPARE_SWAPS: dict[type[ast.cmpop], type[ast.cmpop]] = {
    ast.Lt: ast.GtE,
    ast.LtE: ast.Gt,
    ast.Gt: ast.LtE,
    ast.GtE: ast.Lt,
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
}


@dataclass(frozen=True)
class MutantCandidate:
    """Single source-level AST mutation candidate."""

    rel_file: str
    lineno: int
    description: str
    mutated_source: str
    test_files: tuple[str, ...]


@dataclass
class MutantOutcome:
    """Result of executing mapped tests against a single mutant."""

    rel_file: str
    lineno: int
    description: str
    status: str
    elapsed_s: float


def _collect_mutants_for_file(
    repo: Path, rel_file: str, test_files: list[str], max_per_file: int
) -> list[MutantCandidate]:
    src = (repo / rel_file).read_text(encoding="utf-8")
    base_tree = ast.parse(src, filename=rel_file)
    candidates: list[MutantCandidate] = []

    for idx, node in enumerate(ast.walk(base_tree)):
        if len(candidates) >= max_per_file:
            break
        lineno = getattr(node, "lineno", 0)
        if lineno <= 0:
            continue
        desc: str | None = None
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            swap_cls = COMPARE_SWAPS.get(type(node.ops[0]))
            if swap_cls is not None:
                desc = f"{type(node.ops[0]).__name__} -> {swap_cls.__name__}"
                mutated = _apply_indexed_swap(src, rel_file, idx, swap_compare=swap_cls)
                if mutated is not None:
                    candidates.append(
                        MutantCandidate(rel_file, lineno, desc, mutated, tuple(test_files))
                    )
        elif (
            isinstance(node, ast.Return)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, bool)
        ):
            flipped = not node.value.value
            desc = f"return {node.value.value} -> return {flipped}"
            mutated = _apply_indexed_swap(src, rel_file, idx, flip_bool_return=flipped)
            if mutated is not None:
                candidates.append(
                    MutantCandidate(rel_file, lineno, desc, mutated, tuple(test_files))
                )
    return candidates


def _apply_indexed_swap(
    src: str,
    rel_file: str,
    target_idx: int,
    swap_compare: type[ast.cmpop] | None = None,
    flip_bool_return: bool | None = None,
) -> str | None:
    tree = ast.parse(src, filename=rel_file)
    for idx, node in enumerate(ast.walk(tree)):
        if idx != target_idx:
            continue
        if swap_compare is not None and isinstance(node, ast.Compare):
            # Ignore `if __name__ == "__main__":` guard
            if isinstance(node.left, ast.Name) and node.left.id == "__name__":
                return None
            node.ops = [swap_compare()]
        elif flip_bool_return is not None and isinstance(node, ast.Return):
            node.value = ast.Constant(value=flip_bool_return)
        else:
            return None
        ast.fix_missing_locations(tree)
        out = ast.unparse(tree)
        compile(out, rel_file, "exec")
        return out
    return None


def _stage_alos_overlay(overlay_root: Path, rel_file: str, mutated_source: str) -> None:
    shutil.copytree(
        REPO_ROOT / "alos",
        overlay_root / "alos",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    target = overlay_root / rel_file
    target.write_text(mutated_source, encoding="utf-8")


def _evaluate_mutant(cand: MutantCandidate, timeout_s: float) -> MutantOutcome:
    tmp_dir = Path(tempfile.mkdtemp(prefix="alos_pymut_"))
    started = time.perf_counter()
    try:
        _stage_alos_overlay(tmp_dir, cand.rel_file, cand.mutated_source)
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join([str(tmp_dir), str(REPO_ROOT)])
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        boot = (
            "import os, sys; ov = os.path.abspath(sys.argv.pop(1)); "
            "sys.meta_path[:] = [f for f in sys.meta_path if 'Editable' not in repr(f)]; "
            "sys.path.insert(0, ov); import alos; "
            "assert os.path.abspath(alos.__file__).startswith(ov), alos.__file__; "
            "import pytest; raise SystemExit(pytest.main(sys.argv[1:]))"
        )
        cmd = [
            sys.executable,
            "-c",
            boot,
            str(tmp_dir),
            "-p",
            "no:xdist",
            "-p",
            "no:cov",
            "-o",
            "pythonpath=",
            f"--basetemp={tmp_dir / 'basetemp'}",
            "-x",
            "-q",
            "-m",
            "not docker and not live",
            *cand.test_files,
        ]
        try:
            # Run isolated pytest subprocess against staged mutant overlay without shell.
            proc = subprocess.run(  # noqa: S603  # nosec B603
                cmd,
                cwd=str(REPO_ROOT),
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                check=False,
            )
            status = "killed" if proc.returncode != 0 else "survived"
        except subprocess.TimeoutExpired:
            status = "timeout"
        return MutantOutcome(
            rel_file=cand.rel_file,
            lineno=cand.lineno,
            description=cand.description,
            status=status,
            elapsed_s=round(time.perf_counter() - started, 2),
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cross-platform AST mutation runner for ALOS.")
    parser.add_argument(
        "--modules",
        nargs="*",
        default=list(DEFAULT_TARGETS.keys()),
        help="Target relative module paths",
    )
    parser.add_argument("--max-per-file", type=int, default=3, help="Max mutants sampled per file")
    parser.add_argument(
        "--workers",
        type=int,
        default=2 if os.environ.get("CI", "").lower() == "true" else 1,
        help="Concurrent mutant workers (defaults to 1 locally to avoid workstation load)",
    )
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--min-kill-rate", type=float, default=85.0)
    parser.add_argument("--json-report", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    all_candidates: list[MutantCandidate] = []
    for mod in args.modules:
        tests = DEFAULT_TARGETS.get(mod, ["tests/"])
        all_candidates.extend(_collect_mutants_for_file(REPO_ROOT, mod, tests, args.max_per_file))

    if not all_candidates:
        print("No mutants generated.")
        return 0

    started = time.perf_counter()
    outcomes: list[MutantOutcome] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futs = [pool.submit(_evaluate_mutant, c, args.timeout) for c in all_candidates]
        for fut in as_completed(futs):
            outcomes.append(fut.result())

    outcomes.sort(key=lambda o: (o.rel_file, o.lineno))
    killed = sum(1 for o in outcomes if o.status in ("killed", "timeout"))
    survived = [o for o in outcomes if o.status == "survived"]
    kill_rate = round((killed / len(outcomes)) * 100.0, 2)
    elapsed = round(time.perf_counter() - started, 2)

    for s in survived:
        print(f"  [SURVIVED] {s.rel_file}:{s.lineno} ({s.description})")
    print(
        f"Python mutation summary: {killed}/{len(outcomes)} killed ({kill_rate:.2f}%) "
        f"in {elapsed:.2f}s (threshold >= {args.min_kill_rate:.1f}%)"
    )
    if args.json_report:
        args.json_report.parent.mkdir(parents=True, exist_ok=True)
        args.json_report.write_text(
            json.dumps(
                {
                    "total": len(outcomes),
                    "killed": killed,
                    "survived": len(survived),
                    "kill_rate_pct": kill_rate,
                    "elapsed_s": elapsed,
                    "outcomes": [asdict(o) for o in outcomes],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    return 0 if kill_rate >= args.min_kill_rate else 1


if __name__ == "__main__":
    raise SystemExit(main())
