"""Attempt loop: model drafts a diff, a throwaway worktree applies and tests it, failures feed back.

One queue item goes in; either a diff that passes the item's own tests comes out, or an
escalation that says why every attempt failed. Publishing is a later change (spec 039 PR-7).

Spec: specs/039-self-correcting-build-executor/spec.md
(FR-3901, FR-3903, FR-3906, FR-3914, FR-3920, FR-3921)
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from alos.swarm.build import baseline, leak, triage

ModelCall = Callable[[str], str]
TestRunner = Callable[[Path, Sequence[str], float], baseline.StepResult]

CONTEXT_CHARS = 12000
TEST_PATH = re.compile(r"(^|/)(tests?/|test_[^/]*\.py$|[^/]*_test\.py$)")
FENCE = re.compile(r"```[A-Za-z]*[ \t]*\n(.*?)```", re.S)
DIFF_START = re.compile(r"^--- .*\n\+\+\+ ", re.M)
ADDED_TEST = re.compile(r"\+\s*(?:async\s+)?def test_\w*\(")
SAFE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass
class Attempt:
    number: int
    status: str  # passed, no_diff, leak, apply_failed, tests_failed, no_test_evidence
    feedback: str
    diff: str
    seconds: float
    candidates: int = 1


@dataclass
class BuildResult:
    status: str  # passed or escalated
    reason: str
    attempts: list[Attempt] = field(default_factory=list)
    diff: str = ""
    worktree: str = ""
    baseline_red: bool = False
    triage: dict[str, Any] = field(default_factory=dict)

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


def adds_test(diff: str) -> bool:
    """True if the diff adds a ``def test_...`` line to a test file; touching one is not enough."""
    current, previous = "", ""
    for raw in diff.splitlines():
        if raw.startswith("+++ ") and previous.startswith("--- "):
            current = raw[4:].split("\t")[0].removeprefix("b/")
        elif TEST_PATH.search(current) and ADDED_TEST.match(raw):
            return True
        previous = raw
    return False


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


def build_prompt(
    item: dict[str, Any],
    context: str,
    red: str,
    feedback: str,
    plan: str = "",
    test_first: bool = False,
    layout: str = "",
) -> str:
    """The prompt for one attempt: task, files, test output, and what the last attempt got wrong."""
    lines = [f"Task: {item.get('title', item['id'])}"]
    if item.get("acceptance"):
        lines.append(f"Acceptance: {item['acceptance']}")
    lines.append(f"\nFiles:\n{context}" if context else "\nNo files were named.")
    if red:
        lines.append(f"\nTest output before any change:\n{red}")
    if layout:
        lines.append(f"\nThese files already exist; edit them, never create them again:\n{layout}")
    if plan:
        lines.append(f"\nPlan to follow:\n{plan}")
    if test_first:
        lines.append("\nWrite the failing test first, then the change that makes it pass.")
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
    has_test = adds_test(diff)
    if status == "passed" and not (ctx.baseline_red or has_test):
        return "no_test_evidence", NO_EVIDENCE
    return status, feedback


@dataclass
class _Draw:
    status: str
    feedback: str
    diff: str
    count: int


@dataclass
class _Run:
    runner: TestRunner
    test_command: Sequence[str]
    timeout_s: float
    leak_terms: Sequence[str]
    baseline_red: bool = False


def _plan(item: dict[str, Any], context: str, model: ModelCall) -> str:
    """A short numbered plan, asked for once per item before any diff (FR-3920 plan_first)."""
    task = f"Task: {item.get('title', item['id'])}\nAcceptance: {item.get('acceptance', '')}"
    ask = f"{task}\n\nFiles:\n{context}\n\nWrite a numbered plan of at most 6 short steps. No code."
    return model(ask).strip()[:1500]


def _draw(prompt: str, model: ModelCall, folder: Path, ctx: _Run, count: int) -> _Draw:
    """Up to ``count`` candidate diffs from one prompt; the first that passes the baseline wins."""
    drawn = _Draw("no_diff", "", "", 0)
    for number in range(1, count + 1):
        if number > 1:
            baseline.reset_worktree(folder)
        nudge = (
            f"\n\nCandidate {number} of {count}: take a different approach." if number > 1 else ""
        )
        diff = extract_diff(model(prompt + nudge))
        status, feedback = _judge(diff, folder, ctx)
        drawn = _Draw(status, feedback, diff, number)
        if status == "passed":
            break
    return drawn


def _write_triage(record_dir: Path | None, record: dict[str, Any]) -> None:
    if record_dir is not None:
        record_dir.mkdir(parents=True, exist_ok=True)
        (record_dir / "triage.json").write_text(json.dumps(record, indent=1), encoding="utf-8")


def run_build(
    item: dict[str, Any],
    repo: Path,
    work: Path,
    model: ModelCall,
    *,
    test_command: Sequence[str] = baseline.DEFAULT_TEST_COMMAND,
    attempts: int | None = None,
    runner: TestRunner = baseline.host_tests,
    timeout_s: float = 300.0,
    leak_terms: Sequence[str] = (),
    model_name: str = "",
    record_dir: Path | None = None,
    classify: triage.Classify | None = None,
) -> BuildResult:
    """Triage the item, then try up to its attempt budget; the first passing diff wins."""
    budget, record = triage.triage(item, classify)
    _write_triage(record_dir, record)
    result = BuildResult("escalated", "no attempt ran", triage=record)
    if budget.route == "refine_spec":
        result.status = "refine_spec"
        result.reason = "no testable acceptance or test file; rewrite the item's spec first"
        return result
    limit = budget.attempts if attempts is None else attempts
    slug = SAFE.sub("_", str(item["id"])).strip("_") or "item"
    ctx = _Run(runner, test_command, timeout_s, leak_terms)
    plan = (
        _plan(item, read_context(repo, item.get("files", [])), model) if budget.plan_first else ""
    )
    feedback, red = "", ""
    for n in range(1, limit + 1):
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
            names = item.get("files", [])
            layout = baseline.tracked_near(folder, names)
            prompt = build_prompt(
                item, read_context(folder, names), red, feedback, plan, budget.test_first, layout
            )
            drawn = _draw(prompt, model, folder, ctx, budget.candidates)
            feedback = drawn.feedback
            seconds = round(time.monotonic() - started, 1)
            attempt = Attempt(n, drawn.status, feedback, drawn.diff, seconds, drawn.count)
            result.attempts.append(attempt)
            _record(record_dir, attempt, model_name)
            if drawn.status == "passed":
                keep = True
                result.status, result.reason = "passed", f"passed on attempt {n}"
                result.diff, result.worktree = drawn.diff, str(folder)
                return result
        finally:
            if not keep:
                baseline.remove_worktree(repo, folder, branch)
    if result.attempts:
        last = result.attempts[-1]
        result.reason = f"{limit} attempts failed; last: {last.status}: {last.feedback[:300]}"
    return result
