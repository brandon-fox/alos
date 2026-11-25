"""Attempt loop: model drafts a diff, a throwaway worktree applies and tests it, failures feed back.

One queue item goes in; either a diff that passes the item's own tests comes out, or an
escalation that says why every attempt failed. Publishing is a later change (spec 039 PR-7).

Spec: specs/039-self-correcting-build-executor/spec.md (FR-3901, FR-3903, FR-3906, FR-3914)
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from alos.swarm.build import baseline, leak

ModelCall = Callable[[str], str]
TestRunner = Callable[[Path, Sequence[str], float], baseline.StepResult]

CONTEXT_CHARS = 12000
MAX_ATTEMPTS = 3
TEST_PATH = re.compile(r"(^|/)(tests?/|test_[^/]*\.py$|[^/]*_test\.py$)")
FENCE = re.compile(r"```[A-Za-z]*[ \t]*\n(.*?)```", re.S)
DIFF_START = re.compile(r"^--- .*\n\+\+\+ ", re.M)
NEW_PATH = re.compile(r"^\+\+\+ (?:b/)?(\S+)", re.M)
SAFE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass
class Attempt:
    number: int
    status: str  # passed, no_diff, leak, apply_failed, tests_failed, no_test_evidence
    feedback: str
    diff: str
    seconds: float


@dataclass
class BuildResult:
    status: str  # passed or escalated
    reason: str
    attempts: list[Attempt] = field(default_factory=list)
    diff: str = ""
    worktree: str = ""
    baseline_red: bool = False

    def to_json(self) -> dict[str, Any]:
        return {**asdict(self), "attempt_count": len(self.attempts)}


def extract_diff(answer: str) -> str:
    """Pull one unified diff out of a model answer, fenced or bare; empty if there is none."""
    candidates: list[str] = [*FENCE.findall(answer), answer]
    for candidate in candidates:
        match = DIFF_START.search(candidate)
        if match:
            return candidate[match.start() :].strip() + "\n"
    return ""


def touched_paths(diff: str) -> list[str]:
    """Repo-relative paths a diff writes to."""
    return [p for p in NEW_PATH.findall(diff) if p != "/dev/null"]


def read_context(folder: Path, files: Sequence[str]) -> str:
    """Contents of the files the item names, trimmed to the context budget."""
    root = folder.resolve()
    parts: list[str] = []
    left = CONTEXT_CHARS
    for name in files:
        path = (root / name).resolve()
        if root not in path.parents or not path.is_file() or left <= 0:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")[:left]
        left -= len(text)
        parts.append(f"### {name}\n```\n{text}\n```")
    return "\n\n".join(parts)


def build_prompt(item: dict[str, Any], context: str, red: str, feedback: str) -> str:
    """The prompt for one attempt: task, files, test output, and what the last attempt got wrong."""
    lines = [f"Task: {item.get('title', item['id'])}"]
    if item.get("acceptance"):
        lines.append(f"Acceptance: {item['acceptance']}")
    lines.append(f"\nFiles:\n{context}" if context else "\nNo files were named.")
    if red:
        lines.append(f"\nTest output before any change:\n{red}")
    if feedback:
        lines.append(f"\nYour last attempt failed. Fix that and answer again:\n{feedback}")
    lines.append(
        "\nReply with one unified diff in a ```diff block, paths relative to the repository "
        "root with a/ and b/ prefixes. Change only what the task needs. Add or update a test "
        "that fails without your change. No prose."
    )
    return "\n".join(lines)


def _record(record_dir: Path | None, attempt: Attempt, model_name: str) -> None:
    if record_dir is None:
        return
    record_dir.mkdir(parents=True, exist_ok=True)
    body = {**asdict(attempt), "model": model_name}
    (record_dir / f"attempt-{attempt.number}.json").write_text(
        json.dumps(body, indent=1), encoding="utf-8"
    )


def _check(
    diff: str, folder: Path, terms: Sequence[str], tests: Callable[[], baseline.StepResult]
) -> tuple[str, str]:
    """Run leak, apply and test steps on a diff; return ``(status, feedback)``."""
    findings = leak.scan_diff(diff, terms)
    if findings:
        return "leak", f"The diff adds text that must not be committed: {leak.describe(findings)}"
    applied = baseline.apply_diff(folder, diff)
    if not applied.passed:
        return "apply_failed", f"The diff did not apply:\n{applied.output}"
    result = tests()
    if not result.passed:
        return "tests_failed", f"Tests failed after your change:\n{result.output}"
    return "passed", ""


NO_EVIDENCE = (
    "Tests passed before the change and the diff adds no test. "
    "Add a test that fails without your change."
)


def _judge(diff: str, folder: Path, ctx: _Run) -> tuple[str, str]:
    """Status and feedback for one drafted diff, including the red-green evidence rule."""
    if not diff:
        return "no_diff", "The reply had no unified diff. Reply with one ```diff block."
    status, feedback = _check(
        diff, folder, ctx.leak_terms, lambda: ctx.runner(folder, ctx.test_command, ctx.timeout_s)
    )
    has_test = any(TEST_PATH.search(p) for p in touched_paths(diff))
    if status == "passed" and not (ctx.baseline_red or has_test):
        return "no_test_evidence", NO_EVIDENCE
    return status, feedback


@dataclass
class _Run:
    runner: TestRunner
    test_command: Sequence[str]
    timeout_s: float
    leak_terms: Sequence[str]
    baseline_red: bool = False


def run_build(
    item: dict[str, Any],
    repo: Path,
    work: Path,
    model: ModelCall,
    *,
    test_command: Sequence[str] = baseline.DEFAULT_TEST_COMMAND,
    attempts: int = MAX_ATTEMPTS,
    runner: TestRunner = baseline.host_tests,
    timeout_s: float = 300.0,
    leak_terms: Sequence[str] = (),
    model_name: str = "",
    record_dir: Path | None = None,
) -> BuildResult:
    """Try up to ``attempts`` times; the first diff that applies and passes the tests wins."""
    slug = SAFE.sub("_", str(item["id"])).strip("_") or "item"
    ctx = _Run(runner, test_command, timeout_s, leak_terms)
    result = BuildResult("escalated", "no attempt ran")
    feedback, red = "", ""
    for n in range(1, attempts + 1):
        folder = work / slug / f"attempt-{n}"
        branch = f"alos-build/{slug}-{n}"
        baseline.add_worktree(repo, folder, branch)
        keep = False
        try:
            if n == 1:
                before = runner(folder, test_command, timeout_s)
                ctx.baseline_red = result.baseline_red = not before.passed
                red = "" if before.passed else before.output
            started = time.monotonic()
            prompt = build_prompt(item, read_context(folder, item.get("files", [])), red, feedback)
            diff = extract_diff(model(prompt))
            status, feedback = _judge(diff, folder, ctx)
            attempt = Attempt(n, status, feedback, diff, round(time.monotonic() - started, 1))
            result.attempts.append(attempt)
            _record(record_dir, attempt, model_name)
            if status == "passed":
                keep = True
                result.status, result.reason = "passed", f"passed on attempt {n}"
                result.diff, result.worktree = diff, str(folder)
                return result
        finally:
            if not keep:
                baseline.remove_worktree(repo, folder, branch)
    if result.attempts:
        last = result.attempts[-1]
        result.reason = f"{attempts} attempts failed; last: {last.status}: {last.feedback[:300]}"
    return result
