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
from alos.swarm.build.executor import extract_diff, run_build, touched_paths
from alos.swarm.burn import build_burn_executor
from alos.swarm.dispatcher import Ollama

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is required")


def fenced(head: str, new: str) -> str:
    body = f"def {head}(a, b):\n-    return a - b\n+    return {new}\n"
    return "```diff\n--- a/calc.py\n+++ b/calc.py\n@@ -1,2 +1,2 @@\n " + body + "```"


FIX = fenced("add", "a + b")
STILL_WRONG = fenced("add", "a * b")
NO_MATCH = fenced("plus", "a + b")
ITEM = {"id": "fix add", "title": "add() subtracts", "files": ["calc.py"]}


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
    assert touched_paths("--- a/x\n+++ b/dir/x.py\n--- a/y\n+++ /dev/null\n") == ["dir/x.py"]


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
        payload={"title": "add() subtracts", "files": ["calc.py"], "local_repo_path": str(repo)},
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
