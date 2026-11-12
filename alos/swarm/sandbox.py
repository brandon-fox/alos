"""Sandbox for model-written tests: run one draft inside a locked-down container.

Spec: specs/030-swarm-test-sandbox/spec.md (the spec is the source of truth).

A draft test is code written by a local model, so it is never run on the host. This
module runs it with pytest in a container that has the repository mounted read-only, no
network, a read-only root, no capabilities and an unprivileged user, and reports whether
the draft passes. A passing draft is promoted only if it also fails on at least one
mutant of the code it tests, because a test that cannot fail proves nothing.

Standard library only. Needs a Docker-compatible CLI on PATH and a sandbox image
(``Dockerfile.sandbox``).

Usage:
    python -m alos.swarm.sandbox <plan.json> [--out results.json] [--workers 4]
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
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DOCKER = os.environ.get("ALOS_SANDBOX_DOCKER", "docker")
DEFAULT_IMAGE = os.environ.get("ALOS_SANDBOX_IMAGE", "alos-sandbox:latest")
UNPRIVILEGED = "65534:65534"
DRAFT_PATH = "/drafts/test_draft.py"
ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
COUNT = re.compile(r"(\d+) (passed|failed|error)")
# Exit codes the container runtime uses for its own failures, never for the draft's.
RUNTIME_FAILED = (125, 126, 127)
PYTEST_STATES = {0: "passed", 1: "failed", 5: "empty"}
KILLED_BY = ("failed", "error")
# No cache, no repository config: the draft is the only thing pytest collects.
# A path inside the container (a memory-backed mount), never a temp file on the host.
BOX_TMP = "/tmp"  # noqa: S108  # nosec B108
PYTEST_ARGS = ["-q", "--tb=line", "-p", "no:cacheprovider", "--rootdir", BOX_TMP, "-c", "/dev/null"]


class SandboxError(Exception):
    """The sandbox itself could not run. It says nothing about the draft."""


@dataclass(frozen=True)
class Limits:
    """What one container may use. Every draft and every mutant run gets the same."""

    image: str = DEFAULT_IMAGE
    timeout_s: float = 120.0
    memory: str = "1g"
    cpus: str = "2"
    pids: int = 256


def bind(source: Path, target: str) -> list[str]:
    """A read-only bind mount. A comma would be read as another mount option."""
    if "," in str(source):
        raise SandboxError(f"path contains a comma and cannot be mounted: {source}")
    return ["--mount", f"type=bind,source={source},target={target},readonly"]


def container_argv(
    name: str, repo: Path, draft: Path, limits: Limits, overlay: tuple[str, Path] | None = None
) -> list[str]:
    """Feature: Isolation. The full command line; every isolation rule is a flag here."""
    argv = [DOCKER, "run", "--rm", "--name", name]
    argv += ["--network", "none", "--read-only", "--cap-drop", "ALL"]
    argv += ["--security-opt", "no-new-privileges", "--user", UNPRIVILEGED]
    argv += ["--pids-limit", str(limits.pids), "--memory", limits.memory, "--cpus", limits.cpus]
    argv += ["--tmpfs", f"{BOX_TMP}:rw,size=256m", "--workdir", BOX_TMP]
    for variable in (f"HOME={BOX_TMP}", "PYTHONPATH=/repo", "PYTHONDONTWRITEBYTECODE=1"):
        argv += ["--env", variable]
    argv += bind(repo, "/repo") + bind(draft, DRAFT_PATH)
    if overlay is not None:
        argv += bind(overlay[1], f"/repo/{overlay[0]}")
    return [*argv, limits.image, "python", "-m", "pytest", DRAFT_PATH, *PYTEST_ARGS]


def run_container(argv: list[str], name: str, timeout_s: float) -> tuple[int | None, str]:
    """Run one container. Exit code None means the wall clock ran out and it was killed."""
    try:
        proc = subprocess.run(  # noqa: S603  # nosec B603
            argv, capture_output=True, text=True, timeout=timeout_s, check=False
        )
    except subprocess.TimeoutExpired:
        # The timeout stopped only the client; the container is still running.
        subprocess.run(  # noqa: S603  # nosec B603
            [DOCKER, "kill", name], capture_output=True, timeout=30, check=False
        )
        return None, ""
    except OSError as exc:
        raise SandboxError(f"could not start {DOCKER}: {exc}") from exc
    return proc.returncode, proc.stdout + proc.stderr


def classify(code: int | None, output: str) -> dict[str, Any]:
    """Turn pytest's exit code and last lines into a state. Runtime failures raise."""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    detail = " | ".join(lines[-3:])[-400:]
    if code is None:
        return {"state": "timeout", "passed": 0, "failed": 0, "detail": "wall clock ran out"}
    if code in RUNTIME_FAILED:
        raise SandboxError(f"container runtime failed with exit code {code}: {detail}")
    # The summary is pytest's last line with counts; anything after it is stderr noise.
    summary = next((line for line in reversed(lines) if COUNT.search(line)), "")
    counts = {kind: int(number) for number, kind in COUNT.findall(summary)}
    state = PYTEST_STATES.get(code, "error")
    if state == "passed" and not counts.get("passed"):
        state = "empty"
    return {
        "state": state,
        "passed": counts.get("passed", 0),
        "failed": counts.get("failed", 0) + counts.get("error", 0),
        "detail": detail,
    }


def stage(source: Path, folder: Path, name: str, text: str | None = None) -> Path:
    """Copy a file (or write ``text``) where the unprivileged container user can read it."""
    target = folder / name
    if text is None:
        shutil.copyfile(source, target)
    else:
        target.write_text(text, encoding="utf-8")
    target.chmod(0o644)
    return target


def run_draft(
    repo: Path, draft: Path, limits: Limits, mutant: tuple[str, str] | None = None
) -> dict[str, Any]:
    """Feature: Run a draft. ``mutant`` is (file relative to the repo, mutated source)."""
    started = time.time()
    name = f"alos-sandbox-{uuid.uuid4().hex[:12]}"
    with tempfile.TemporaryDirectory(prefix="alos-sandbox-") as tmp:
        folder = Path(tmp)
        folder.chmod(0o755)
        staged = stage(draft, folder, "test_draft.py")
        overlay = None
        if mutant is not None:
            overlay = (mutant[0], stage(draft, folder, "mutant.py", mutant[1]))
        argv = container_argv(name, repo.resolve(), staged, limits, overlay)
        code, output = run_container(argv, name, limits.timeout_s)
    return {**classify(code, output), "seconds": round(time.time() - started, 1)}


def mutate(source: str, line: str, mutated: str) -> str | None:
    """Replace the first line equal to ``line``, keeping its indentation. None if it cannot."""
    want, new = line.strip(), mutated.strip()
    if not want or want == new:
        return None
    lines = source.splitlines(keepends=True)
    for index, current in enumerate(lines):
        if current.strip() == want:
            indent = current[: len(current) - len(current.lstrip())]
            lines[index] = f"{indent}{new}" + ("\n" if current.endswith("\n") else "")
            return "".join(lines)
    return None


def mutant_source(repo: Path, mutant: dict[str, Any]) -> tuple[str | None, str]:
    """Return (mutated source, "") or (None, why this mutant cannot be tried)."""
    rel = str(mutant.get("file", ""))
    target = (repo / rel).resolve()
    if not rel or not target.is_relative_to(repo.resolve()) or not target.is_file():
        return None, "not_found"
    changed = mutate(
        target.read_text(encoding="utf-8", errors="replace"),
        str(mutant.get("line", "")),
        str(mutant.get("mutated", "")),
    )
    if changed is None:
        return None, "not_found"
    try:
        compile(changed, rel, "exec")
    except (SyntaxError, ValueError):
        return None, "invalid"
    return changed, ""


def run_mutant(repo: Path, draft: Path, limits: Limits, mutant: dict[str, Any]) -> dict[str, Any]:
    """Feature: A kept test must be able to fail. One mutant, one container."""
    changed, why = mutant_source(repo, mutant)
    report = {"file": mutant.get("file", ""), "line": mutant.get("line", "")}
    if changed is None:
        return {**report, "state": why}
    rel = (repo / str(mutant["file"])).resolve().relative_to(repo.resolve()).as_posix()
    result = run_draft(repo, draft, limits, (rel, changed))
    killed = result["state"] in KILLED_BY
    state = "killed" if killed else "survived" if result["state"] == "passed" else result["state"]
    return {**report, "state": state}


def check_job(job: dict[str, Any], limits: Limits) -> dict[str, Any]:
    """One draft: run it, and if it passes, try each planned mutant against it."""
    repo, draft = Path(job["repo"]), Path(job["test"])
    if not repo.is_dir() or not draft.is_file():
        return {"id": job["id"], "state": "error", "detail": "repo or test path does not exist"}
    result: dict[str, Any] = {"id": job["id"], **run_draft(repo, draft, limits)}
    result["mutants"] = []
    if result["state"] == "passed":
        result["mutants"] = [run_mutant(repo, draft, limits, m) for m in job.get("mutants", [])]
    result["promote"] = any(m["state"] == "killed" for m in result["mutants"])
    return result


def require_image(image: str) -> None:
    """Fail before any draft runs if the runtime or the image is missing."""
    try:
        proc = subprocess.run(  # noqa: S603  # nosec B603
            [DOCKER, "image", "inspect", image], capture_output=True, timeout=60, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SandboxError(f"could not reach {DOCKER}: {exc}") from exc
    if proc.returncode != 0:
        raise SandboxError(
            f"sandbox image {image!r} is not available; build it from Dockerfile.sandbox"
        )


def run_plan(plan: dict[str, Any], workers: int = 4) -> dict[str, Any]:
    """Run every job in a plan and summarise. A runtime failure stops the whole plan."""
    limits = Limits(
        image=str(plan.get("image", DEFAULT_IMAGE)), timeout_s=float(plan.get("timeout_s", 120))
    )
    jobs = plan.get("jobs", [])
    for job in jobs:
        if not ID_PATTERN.match(str(job.get("id", ""))):
            raise SandboxError(f"job id {job.get('id')!r} must match {ID_PATTERN.pattern}")
    require_image(limits.image)
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        results = list(pool.map(lambda job: check_job(job, limits), jobs))
    counts: dict[str, int] = {}
    for result in results:
        counts[result["state"]] = counts.get(result["state"], 0) + 1
    return {
        "image": limits.image,
        "counts": counts,
        "promoted": sum(1 for result in results if result.get("promote")),
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    """Command line entry: run a plan file and write the results beside it."""
    parser = argparse.ArgumentParser(description="Run draft tests in a locked-down container.")
    parser.add_argument("plan", type=Path, help="plan.json listing the drafts to run")
    parser.add_argument("--out", type=Path, help="where to write results (default: beside plan)")
    parser.add_argument("--workers", type=int, default=4, help="containers to run at once")
    args = parser.parse_args(argv)
    try:
        plan = json.loads(args.plan.read_text(encoding="utf-8-sig"))
        summary = run_plan(plan, args.workers)
    except (SandboxError, OSError, ValueError) as exc:
        print(f"sandbox error: {exc}", file=sys.stderr)
        return 2
    out = args.out or args.plan.with_name("sandbox-results.json")
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"{summary['counts']} promoted={summary['promoted']} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
