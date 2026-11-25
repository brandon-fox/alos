"""Build executor attempt loop against a real git fixture and a scripted model.

Spec: specs/039-self-correcting-build-executor/spec.md (FR-3901, FR-3906, FR-3914)
"""

from __future__ import annotations

import json
import shutil
import threading
from pathlib import Path

import pytest

from alos.runtime import RuntimePaths
from alos.swarm import queue as queue_mod
from alos.swarm.build import baseline
from alos.swarm.build.executor import adds_test, extract_diff, run_build
from alos.swarm.burn import build_burn_executor
from alos.swarm.dispatcher import Ollama

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is required")


def fenced(head: str, new: str) -> str:
    body = f"def {head}(a, b):\n-    return a - b\n+    return {new}\n"
    return "```diff\n--- a/calc.py\n+++ b/calc.py\n@@ -1,2 +1,2 @@\n " + body + "```"


FIX = fenced("add", "a + b")
STILL_WRONG = fenced("add", "a * b")
NO_MATCH = fenced("plus", "a + b")
ITEM = {
    "id": "fix add",
    "title": "add() subtracts",
    "acceptance": "add(2, 3) == 5",
    "files": ["calc.py"],
}


def run(repo: Path, *args: str) -> None:
    code, out = baseline.git(repo, *args)
    assert code == 0, out


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (root / "test_calc.py").write_text(
        "from calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n", encoding="utf-8"
    )
    run(root, "init", "-q", "-b", "main")
    run(root, "config", "user.name", "t")
    run(root, "config", "user.email", "t@users.noreply.github.com")
    run(root, "add", "calc.py", "test_calc.py")
    run(root, "commit", "-q", "-m", "fixture")
    return root


class Scripted:
    def __init__(self, *answers: str) -> None:
        self.answers = list(answers)
        self.prompts: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.answers.pop(0)


def test_extract_diff_fenced_bare_and_missing() -> None:
    assert extract_diff("Here:\n" + FIX + "\nDone").startswith("--- a/calc.py\n+++ b/calc.py")
    assert extract_diff("--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b").endswith("+b\n")
    assert extract_diff("I could not find a fix.") == ""


def test_first_attempt_passes_and_leaves_the_repo_alone(repo: Path, tmp_path: Path) -> None:
    model = Scripted(FIX)
    res = run_build(ITEM, repo, tmp_path / "work", model)
    assert (res.status, len(res.attempts), res.baseline_red) == ("passed", 1, True)
    assert "return a + b" in (Path(res.worktree) / "calc.py").read_text(encoding="utf-8")
    assert "a - b" in (repo / "calc.py").read_text(encoding="utf-8")
    assert "assert" in model.prompts[0] and "def add" in model.prompts[0]


def test_failure_output_feeds_the_next_attempt(repo: Path, tmp_path: Path) -> None:
    model = Scripted(STILL_WRONG, FIX)
    res = run_build(ITEM, repo, tmp_path / "work", model)
    assert [a.status for a in res.attempts] == ["tests_failed", "passed"]
    assert "6 == 5" in model.prompts[1]
    assert not (tmp_path / "work" / "fix_add" / "attempt-1").exists()


def test_unappliable_diff_is_reported_back(repo: Path, tmp_path: Path) -> None:
    model = Scripted(NO_MATCH, FIX)
    res = run_build(ITEM, repo, tmp_path / "work", model)
    assert [a.status for a in res.attempts] == ["apply_failed", "passed"]
    assert "did not apply" in model.prompts[1]


def test_escalates_after_the_attempt_limit_and_cleans_up(repo: Path, tmp_path: Path) -> None:
    res = run_build(ITEM, repo, tmp_path / "work", Scripted(STILL_WRONG, "no idea", NO_MATCH))
    assert res.status == "escalated"
    assert [a.status for a in res.attempts] == ["tests_failed", "no_diff", "apply_failed"]
    assert "3 attempts failed" in res.reason
    assert not list((tmp_path / "work").rglob("calc.py"))
    _, branches = baseline.git(repo, "branch", "--list", "alos-build/*")
    assert branches.strip() == ""


def test_a_diff_with_a_leak_never_reaches_the_worktree(repo: Path, tmp_path: Path) -> None:
    leaky = FIX.replace("+    return a + b", "+    return a + b  # a@" + "gmail.com")
    res = run_build(ITEM, repo, tmp_path / "work", Scripted(leaky, FIX))
    assert [a.status for a in res.attempts] == ["leak", "passed"]


def passing(_folder: Path, _cmd: object, _timeout: float) -> baseline.StepResult:
    return baseline.StepResult("tests", True, "1 passed")


def test_green_before_and_no_new_test_is_not_evidence(repo: Path, tmp_path: Path) -> None:
    res = run_build(ITEM, repo, tmp_path / "work", Scripted(FIX), attempts=1, runner=passing)
    assert (res.status, res.attempts[0].status, res.baseline_red) == (
        "escalated",
        "no_test_evidence",
        False,
    )


def test_each_attempt_is_recorded(repo: Path, tmp_path: Path) -> None:
    rec = tmp_path / "records"
    run_build(
        ITEM, repo, tmp_path / "work", Scripted(STILL_WRONG, FIX), model_name="m", record_dir=rec
    )
    first = json.loads((rec / "attempt-1.json").read_text(encoding="utf-8"))
    assert (first["status"], first["model"], "a * b" in first["diff"]) == (
        "tests_failed",
        "m",
        True,
    )
    assert (rec / "attempt-2.json").is_file()


def test_missing_test_command_is_an_environment_error_not_a_model_failure(
    repo: Path, tmp_path: Path
) -> None:
    with pytest.raises(baseline.BuildError):
        run_build(ITEM, repo, tmp_path / "work", Scripted(FIX), test_command=["no-such-tool-xyz"])


def build_job(repo: Path) -> queue_mod.LeasedJob:
    return queue_mod.LeasedJob(
        job_id="build-1",
        repo_slug="fixture",
        workflow_type="build",
        model_tier="architect",
        priority=50,
        requires_merge=False,
        allow_cloud_overflow=False,
        payload={
            "title": "add() subtracts",
            "acceptance": "add(2, 3) == 5",
            "files": ["calc.py"],
            "local_repo_path": str(repo),
        },
        checkpoint_ns=None,
        state="leased",
        attempts=1,
        max_attempts=2,
    )


def test_queue_build_job_refuses_to_run_tests_on_the_host_unless_allowed(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ALOS_BUILD_UNSANDBOXED", raising=False)
    execute = build_burn_executor(RuntimePaths.resolve(str(tmp_path / "home")))
    with pytest.raises(RuntimeError, match="ALOS_BUILD_UNSANDBOXED"):
        execute(build_job(repo), Ollama("http://127.0.0.1:1"), threading.Event())


def test_queue_build_job_runs_the_loop_and_traces_each_model_call(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALOS_BUILD_UNSANDBOXED", "1")
    answers = [STILL_WRONG, FIX]

    def fake_generate(job: object, _client: object, _cancel: object) -> dict[str, object]:
        trace = {"prompt_tokens": 10, "answer_tokens": 5, "total_ms": 1.0}
        return {"response": answers.pop(0), "model": "fake", "done_reason": "stop", "trace": trace}

    monkeypatch.setattr(queue_mod, "default_prompt_executor", fake_generate)
    paths = RuntimePaths.resolve(str(tmp_path / "home"))
    out = build_burn_executor(paths)(
        build_job(repo), Ollama("http://127.0.0.1:1"), threading.Event()
    )
    assert (out["status"], out["attempt_count"], out["model"]) == ("passed", 2, "fake")
    lines = (paths.logs_dir / "generation_trace.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert (paths.results_dir / "fixture" / "build-1" / "attempt-2.json").is_file()


TEST_FILE = (
    "diff --git a/test_calc.py b/test_calc.py\n--- a/test_calc.py\n+++ b/test_calc.py\n"
    "@@ -3,3 +3,{n} @@\n \n def test_add():\n     assert add(2, 3) == 5\n"
)


def with_test_file(extra: str, new_count: int) -> str:
    """The calc fix plus an edit to the test file, as one model answer."""
    fix = FIX.removesuffix("```")
    return fix + TEST_FILE.replace("{n}", str(new_count)) + extra + "```"


def test_adds_test_needs_a_new_test_function_in_a_test_file() -> None:
    comment = TEST_FILE.replace("{n}", "4") + "+# note\n"
    real = TEST_FILE.replace("{n}", "6") + "+\n+def test_add_zero():\n+    assert add(0, 0) == 0\n"
    in_code = "--- a/calc.py\n+++ b/calc.py\n@@ -1 +1 @@\n-x\n+def test_x():\n"
    assert not adds_test(comment)
    assert adds_test(real)
    assert not adds_test(in_code)


def test_a_comment_in_the_test_file_is_not_test_evidence(repo: Path, tmp_path: Path) -> None:
    answer = with_test_file("+# note\n", 4)
    res = run_build(ITEM, repo, tmp_path / "work", Scripted(answer), attempts=1, runner=passing)
    assert res.attempts[0].status == "no_test_evidence"


def test_an_added_test_function_is_test_evidence(repo: Path, tmp_path: Path) -> None:
    answer = with_test_file("+\n+def test_add_zero():\n+    assert add(0, 0) == 0\n", 6)
    res = run_build(ITEM, repo, tmp_path / "work", Scripted(answer), attempts=1, runner=passing)
    assert res.status == "passed"


def test_a_build_job_cancelled_before_it_starts_creates_nothing(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALOS_BUILD_UNSANDBOXED", "1")
    paths = RuntimePaths.resolve(str(tmp_path / "home"))
    stop = threading.Event()
    stop.set()
    with pytest.raises(queue_mod.PreemptedExecutionError):
        build_burn_executor(paths)(build_job(repo), Ollama("http://127.0.0.1:1"), stop)
    assert not (paths.root / "worktrees").exists()


def test_underspecified_item_runs_no_attempt_and_asks_for_a_spec(
    repo: Path, tmp_path: Path
) -> None:
    model = Scripted()
    bare = {"id": "vague", "title": "make it better", "files": []}
    res = run_build(bare, repo, tmp_path / "work", model)
    assert (res.status, res.attempts, model.prompts) == ("refine_spec", [], [])
    assert res.triage["label"] == "underspecified"


def test_candidates_share_one_attempt_and_the_passing_one_is_kept(
    repo: Path, tmp_path: Path
) -> None:
    item = {**ITEM, "files": ["calc.py", "a.py", "b.py"]}
    model = Scripted("plan: fix add", NO_MATCH, STILL_WRONG, FIX)
    rec = tmp_path / "rec"
    res = run_build(item, repo, tmp_path / "work", model, record_dir=rec)
    assert (res.status, len(res.attempts), res.attempts[0].candidates) == ("passed", 1, 3)
    assert "Plan to follow:\nplan: fix add" in model.prompts[1]
    assert "Candidate 3 of 3" in model.prompts[3]
    assert json.loads((rec / "triage.json").read_text())["label"] == "multi_file"


def test_a_candidate_starts_from_a_clean_worktree(repo: Path, tmp_path: Path) -> None:
    item = {**ITEM, "files": ["calc.py", "a.py", "b.py"]}
    res = run_build(item, repo, tmp_path / "work", Scripted("plan", STILL_WRONG, FIX))
    assert res.status == "passed"
    assert res.diff == extract_diff(FIX)


def test_explicit_attempts_override_the_triage_budget(repo: Path, tmp_path: Path) -> None:
    res = run_build(ITEM, repo, tmp_path / "work", Scripted(NO_MATCH, FIX), attempts=1)
    assert (res.status, len(res.attempts)) == ("escalated", 1)
