"""Cross-platform parallel Behave BDD orchestrator with @live hardware lane serialization.

Spec: specs/035-parallel-testing-and-qa-matrix/spec.md (FR-003, FR-009)
ADR: ADR-0019
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess  # nosec B404
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path

SCENARIO_RE = re.compile(r"^\s*Scenario(?: Outline)?:\s*(.+)$")
FEATURE_RE = re.compile(r"^\s*Feature:\s*(.+)$")
TAG_TOKEN_RE = re.compile(r"@([A-Za-z0-9_.-]+)")


@dataclass(frozen=True)
class ScenarioTarget:
    """Single addressable Behave scenario with resolved feature + scenario tags."""

    feature_path: str
    line: int
    feature_name: str
    scenario_name: str
    tags: frozenset[str]

    @property
    def location(self) -> str:
        return f"{self.feature_path}:{self.line}"

    @property
    def is_live_or_hardware(self) -> bool:
        return bool(self.tags & {"live", "docker_live", "docker_only"})


@dataclass
class ScenarioResult:
    """Execution result for a single Behave scenario subprocess."""

    location: str
    scenario_name: str
    tags: list[str]
    status: str
    elapsed_s: float
    returncode: int
    stdout: str
    stderr: str


def discover_scenarios(features_dir: Path) -> list[ScenarioTarget]:
    """Parse Gherkin feature files to discover scenarios and effective inherited tags."""
    targets: list[ScenarioTarget] = []
    for fpath in sorted(features_dir.glob("*.feature")):
        lines = fpath.read_text(encoding="utf-8").splitlines()
        pending_tags: list[str] = []
        feature_tags: set[str] = set()
        feature_name = fpath.stem

        for idx, raw in enumerate(lines, 1):
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("@"):
                pending_tags.extend(TAG_TOKEN_RE.findall(stripped))
                continue
            f_match = FEATURE_RE.match(raw)
            if f_match:
                feature_name = f_match.group(1).strip()
                feature_tags = set(pending_tags)
                pending_tags.clear()
                continue
            s_match = SCENARIO_RE.match(raw)
            if s_match:
                eff_tags = frozenset(feature_tags | set(pending_tags))
                pending_tags.clear()
                targets.append(
                    ScenarioTarget(
                        feature_path=fpath.as_posix(),
                        line=idx,
                        feature_name=feature_name,
                        scenario_name=s_match.group(1).strip(),
                        tags=eff_tags,
                    )
                )
    return targets


def _matches_tag_expr(tags: frozenset[str], expr: str | None) -> bool:
    """Evaluate Behave-compatible boolean tag expressions (e.g. '@mocked', 'not @live')."""
    if not expr or not expr.strip():
        return True
    normalized = expr.strip()
    # Support comma-separated OR clauses in classic Behave syntax (e.g. "@smoke,@mocked")
    if "," in normalized and " and " not in normalized and " or " not in normalized:
        parts = [p.strip() for p in normalized.split(",") if p.strip()]
        return any(_matches_tag_expr(tags, part) for part in parts)

    def _repl(match: re.Match[str]) -> str:
        tag_name = match.group(1)
        return "True" if tag_name in tags else "False"

    py_expr = re.sub(r"@([A-Za-z0-9_.-]+)", _repl, normalized)
    py_expr = re.sub(
        r"~([A-Za-z0-9_.-]+)",
        lambda m: f"(not {'True' if m.group(1) in tags else 'False'})",
        py_expr,
    )
    allowed = set("TrueFalsnotand() ")
    if not set(py_expr).issubset(allowed | set("eor")):
        raise ValueError(f"Unsupported tag expression: {expr!r}")
    return bool(eval(py_expr, {"__builtins__": {}}, {}))  # noqa: S307  # nosec B307


def _run_one_scenario(
    target: ScenarioTarget,
    cov_enabled: bool,
    cov_file: Path | None,
    require_live: bool,
    seed: int | None,
) -> ScenarioResult:
    worker_tmp = Path(tempfile.mkdtemp(prefix="alos_bworker_"))
    started = time.perf_counter()
    env = dict(os.environ)
    iso_home = worker_tmp / "home"
    (iso_home / "logs").mkdir(parents=True, exist_ok=True)
    env["ALOS_HOME"] = str(iso_home)
    env["ALOS_AUDIT_LOG_PATH"] = str(iso_home / "logs" / "system_audit.jsonl")
    env["ALOS_DECISION_LOG_PATH"] = str(iso_home / "logs" / "decision_log.jsonl")
    if require_live:
        env["ALOS_REQUIRE_LIVE"] = "1"
    if seed is not None:
        env["PYTHONHASHSEED"] = str(seed)
    if cov_enabled and cov_file is not None:
        env["COVERAGE_FILE"] = str(cov_file)

    cmd = [sys.executable, "-m"]
    if cov_enabled:
        cmd.extend(["coverage", "run", "--parallel-mode", "-m"])
    cmd.extend(["behave", target.location, "--no-capture", "-f", "plain"])
    if require_live:
        cmd.extend(["-D", "require_live=1"])

    try:
        # Execute isolated Behave scenario subprocess using sys.executable without shell.
        proc = subprocess.run(  # noqa: S603  # nosec B603
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
            env=env,
        )
        elapsed = round(time.perf_counter() - started, 3)
        out = proc.stdout or ""
        if proc.returncode != 0:
            status = "failed"
        elif "0 scenarios passed, 0 failed, 1 skipped" in out:
            status = "skipped"
        else:
            status = "passed"
        return ScenarioResult(
            location=target.location,
            scenario_name=target.scenario_name,
            tags=sorted(target.tags),
            status=status,
            elapsed_s=elapsed,
            returncode=proc.returncode,
            stdout=out,
            stderr=proc.stderr or "",
        )
    finally:
        shutil.rmtree(worker_tmp, ignore_errors=True)


def _write_junit_xml(path: Path, results: list[ScenarioResult], total_s: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    failures = sum(1 for r in results if r.status == "failed")
    skipped = sum(1 for r in results if r.status == "skipped")
    suite = ET.Element(
        "testsuite",
        name="alos-behave-parallel",
        tests=str(len(results)),
        failures=str(failures),
        skipped=str(skipped),
        time=f"{total_s:.3f}",
    )
    for res in results:
        case = ET.SubElement(
            suite,
            "testcase",
            classname=res.location.split(":")[0],
            name=res.scenario_name,
            time=f"{res.elapsed_s:.3f}",
        )
        if res.status == "skipped":
            ET.SubElement(case, "skipped", message="Scenario skipped")
        elif res.status == "failed":
            fail = ET.SubElement(case, "failure", message=f"Exited with {res.returncode}")
            fail.text = f"{res.stdout}\n{res.stderr}".strip()
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def _resolve_profile_tags(profile: str | None, explicit_tags: str | None) -> str | None:
    if explicit_tags:
        return explicit_tags
    mapping = {
        "mocked": "@mocked and not @live",
        "live": "@live",
        "smoke": "@smoke or @mocked",
        "full": None,
    }
    return mapping.get(profile or "", explicit_tags)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parallel cross-platform Behave runner for ALOS.")
    parser.add_argument("--features-dir", type=Path, default=Path("features"))
    parser.add_argument("--tags", type=str, default=None, help="Behave boolean tag filter")
    parser.add_argument(
        "--profile",
        choices=["mocked", "live", "smoke", "full"],
        default=None,
        help="Named behavior profile",
    )
    parser.add_argument("--workers", type=int, default=0, help="Max parallel mocked workers")
    parser.add_argument("--cov", action="store_true", help="Collect parallel coverage.py shards")
    parser.add_argument("--require-live", action="store_true", help="Fail if @live is skipped")
    parser.add_argument("--seed", type=int, default=None, help="Deterministic seed")
    parser.add_argument("--junit-xml", type=Path, default=None, help="Write JUnit XML report")
    parser.add_argument("--json-report", type=Path, default=None, help="Write JSON summary report")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    tag_expr = _resolve_profile_tags(args.profile, args.tags)
    all_targets = discover_scenarios(args.features_dir)
    selected = [t for t in all_targets if _matches_tag_expr(t.tags, tag_expr)]
    if not selected:
        print(f"No Behave scenarios matched tags={tag_expr!r}.")
        return 0

    mocked_lane = [t for t in selected if not t.is_live_or_hardware]
    live_lane = [t for t in selected if t.is_live_or_hardware]
    in_ci = os.environ.get("CI", "").lower() == "true"
    default_cap = 4 if in_ci else 2
    workers = args.workers or min(os.cpu_count() or 2, max(1, len(mocked_lane)), default_cap)

    cov_root = Path(tempfile.mkdtemp(prefix="alos_behave_cov_")) if args.cov else None
    cov_base = (cov_root / ".coverage") if cov_root else None

    started = time.perf_counter()
    results: list[ScenarioResult] = []
    try:
        if mocked_lane:
            with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
                futs = {
                    pool.submit(
                        _run_one_scenario, t, args.cov, cov_base, args.require_live, args.seed
                    ): t
                    for t in mocked_lane
                }
                for fut in as_completed(futs):
                    results.append(fut.result())

        # Hardware-serialized lane: @live / @docker_live never contend for single-GPU VRAM
        for target in live_lane:
            results.append(
                _run_one_scenario(target, args.cov, cov_base, args.require_live, args.seed)
            )

        if args.cov and cov_base is not None:
            env = dict(os.environ, COVERAGE_FILE=str(cov_base))
            # Combine parallel subprocess coverage shards without shell.
            subprocess.run(  # nosec B603
                [sys.executable, "-m", "coverage", "combine"],
                env=env,
                capture_output=True,
                check=False,
            )
            if cov_base.exists():
                shutil.copy2(cov_base, Path.cwd() / ".coverage.behave")
    finally:
        if cov_root is not None:
            shutil.rmtree(cov_root, ignore_errors=True)

    results.sort(key=lambda r: r.location)
    total_s = round(time.perf_counter() - started, 2)
    passed = sum(1 for r in results if r.status == "passed")
    skipped = sum(1 for r in results if r.status == "skipped")
    failed = sum(1 for r in results if r.status == "failed")

    for res in results:
        badge = {"passed": "PASS", "skipped": "SKIP", "failed": "FAIL"}[res.status]
        print(f"  [{badge}] {res.location} ({res.elapsed_s:.2f}s) — {res.scenario_name}")
        if res.status == "failed":
            print(f"--- STDOUT ({res.location}) ---\n{res.stdout}\n--- STDERR ---\n{res.stderr}")

    print(
        f"\nBehave parallel summary (workers={workers}, live_serial={len(live_lane)}): "
        f"{passed} passed, {failed} failed, {skipped} skipped in {total_s:.2f}s"
    )
    if args.junit_xml:
        _write_junit_xml(args.junit_xml, results, total_s)
    if args.json_report:
        args.json_report.parent.mkdir(parents=True, exist_ok=True)
        args.json_report.write_text(
            json.dumps(
                {
                    "elapsed_s": total_s,
                    "workers": workers,
                    "passed": passed,
                    "failed": failed,
                    "skipped": skipped,
                    "scenarios": [asdict(r) for r in results],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
