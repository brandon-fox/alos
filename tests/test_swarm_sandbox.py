"""Tests for the draft-test sandbox (specs/030-swarm-test-sandbox).

Unit tests need nothing but Python. Tests marked ``docker`` start real containers; they
run when ALOS_SANDBOX_IMAGE names an image that exists locally and are skipped otherwise.
With ALOS_SANDBOX_REQUIRED=1 a missing image is a failure, so CI cannot pass by skipping.
"""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from alos.swarm import sandbox
from alos.swarm.sandbox import Limits, SandboxError

IMAGE = os.environ.get("ALOS_SANDBOX_IMAGE", "")
SOURCE = (
    "def clamp(value, low, high):\n"
    "    if value < low:\n"
    "        return low\n"
    "    return min(value, high)\n"
)
PASSING = (
    "from pkg.calc import clamp\n\n"
    "def test_clamps_high():\n    assert clamp(5, 0, 3) == 3\n\n"
    "def test_clamps_low():\n    assert clamp(-1, 0, 3) == 0\n"
)
# Every test here passes only if the sandbox blocked the attempt.
HOSTILE = (
    "import os\nimport socket\n\nimport pytest\n\n"
    "def test_cannot_delete_a_repository_file():\n"
    "    with pytest.raises(OSError):\n        os.remove('/repo/pkg/calc.py')\n\n"
    "def test_cannot_write_into_the_repository():\n"
    "    with pytest.raises(OSError):\n        open('/repo/planted.txt', 'w')\n\n"
    "def test_cannot_write_outside_tmp():\n"
    "    with pytest.raises(OSError):\n        open('/planted.txt', 'w')\n\n"
    "def test_cannot_reach_the_network():\n"
    "    with pytest.raises(OSError):\n"
    "        socket.create_connection(('1.1.1.1', 53), timeout=3)\n\n"
    "def test_is_not_root():\n    assert os.getuid() != 0\n"
)
# No manners: destroys what it can while being imported.
RUDE = (
    "import shutil\n\n"
    "shutil.rmtree('/repo', ignore_errors=True)\n"
    "open('/repo/pkg/calc.py', 'w').write('gone')\n\n"
    "def test_never_reached():\n    assert True\n"
)


def docker_ready() -> bool:
    if not IMAGE or not shutil.which("docker"):
        return False
    proc = subprocess.run(  # noqa: S603
        ["docker", "image", "inspect", IMAGE],  # noqa: S607
        capture_output=True,
        check=False,
    )
    return proc.returncode == 0


READY = docker_ready()
needs_docker = pytest.mark.skipif(
    not READY and os.environ.get("ALOS_SANDBOX_REQUIRED") != "1",
    reason="set ALOS_SANDBOX_IMAGE to a local sandbox image to run container tests",
)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A tiny repository the unprivileged container user is allowed to read."""
    root = tmp_path / "repo"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (root / "pkg" / "calc.py").write_text(SOURCE, encoding="utf-8")
    for path in [root, *root.rglob("*")]:
        path.chmod(0o755 if path.is_dir() else 0o644)
    return root


def draft(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "draft.py"
    path.write_text(text, encoding="utf-8")
    return path


def digest(root: Path) -> str:
    """One hash over every path and file content under ``root``."""
    seen = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        seen.update(path.relative_to(root).as_posix().encode())
        if path.is_file():
            seen.update(path.read_bytes())
    return seen.hexdigest()


# --- Unit tests: no container runtime needed ------------------------------------------


def test_container_argv_carries_every_isolation_rule(tmp_path: Path) -> None:
    argv = sandbox.container_argv("n1", tmp_path, tmp_path / "t.py", Limits(image="img"))
    joined = " ".join(argv)
    for flag in (
        "--network none",
        "--read-only",
        "--cap-drop ALL",
        "--security-opt no-new-privileges",
        "--user 65534:65534",
        "--pids-limit 256",
        "--memory 1g",
        "--rm",
    ):
        assert flag in joined
    mounts = [arg for arg in argv if arg.startswith("type=bind")]
    assert len(mounts) == 2
    assert all(mount.endswith(",readonly") for mount in mounts)
    assert argv[argv.index("img") + 1 :][:3] == ["python", "-m", "pytest"]


def test_a_mutant_is_mounted_read_only_over_the_file_it_replaces(tmp_path: Path) -> None:
    overlay = ("pkg/calc.py", tmp_path / "mutant.py")
    argv = sandbox.container_argv("n1", tmp_path, tmp_path / "t.py", Limits(), overlay)
    assert f"type=bind,source={tmp_path / 'mutant.py'},target=/repo/pkg/calc.py,readonly" in argv


def test_a_path_with_a_comma_is_refused_rather_than_misread() -> None:
    with pytest.raises(SandboxError, match="comma"):
        sandbox.bind(Path("/work/a,b"), "/repo")


@pytest.mark.parametrize(
    ("code", "output", "state"),
    [
        (0, "..\n2 passed in 0.01s", "passed"),
        (1, "F.\n1 failed, 1 passed in 0.02s", "failed"),
        (2, "ERROR collecting\n1 error in 0.05s", "error"),
        (5, "no tests ran in 0.00s", "empty"),
        (0, "no tests ran in 0.00s", "empty"),
        (137, "", "error"),
        (None, "", "timeout"),
    ],
)
def test_classify_maps_pytest_exit_codes_to_draft_states(
    code: int | None, output: str, state: str
) -> None:
    assert sandbox.classify(code, output)["state"] == state


def test_classify_counts_passed_and_failed() -> None:
    result = sandbox.classify(1, "1 failed, 3 passed, 1 error in 0.1s")
    assert (result["passed"], result["failed"]) == (3, 2)


@pytest.mark.parametrize("code", [125, 126, 127])
def test_a_runtime_failure_is_the_sandbox_failing_not_the_draft(code: int) -> None:
    with pytest.raises(SandboxError, match=str(code)):
        sandbox.classify(code, "docker: Error response from daemon")


def test_mutate_replaces_the_first_matching_line_and_keeps_indentation() -> None:
    changed = sandbox.mutate(SOURCE, "return min(value, high)", "return max(value, high)")
    assert changed is not None
    assert "    return max(value, high)\n" in changed
    assert changed.count("\n") == SOURCE.count("\n")


def test_mutate_refuses_a_line_that_is_absent_or_unchanged() -> None:
    assert sandbox.mutate(SOURCE, "return value", "return 0") is None
    assert sandbox.mutate(SOURCE, "return low", "return low") is None
    assert sandbox.mutate(SOURCE, "  ", "return 0") is None


def test_mutant_source_rejects_escapes_and_code_that_does_not_compile(repo: Path) -> None:
    outside = {"file": "../secret.py", "line": "x", "mutated": "y"}
    broken = {"file": "pkg/calc.py", "line": "return low", "mutated": "return ("}
    missing = {"file": "pkg/calc.py", "line": "return nothing", "mutated": "return 1"}
    assert sandbox.mutant_source(repo, outside) == (None, "not_found")
    assert sandbox.mutant_source(repo, broken) == (None, "invalid")
    assert sandbox.mutant_source(repo, missing) == (None, "not_found")


def test_run_container_kills_the_container_by_name_when_the_clock_runs_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    def fake_run(argv: list[str], **kwargs: Any) -> Any:
        calls.append(argv)
        if argv[1] == "run":
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(sandbox.subprocess, "run", fake_run)
    assert sandbox.run_container([sandbox.DOCKER, "run", "x"], "box-1", 0.1) == (None, "")
    assert calls[-1] == [sandbox.DOCKER, "kill", "box-1"]


def test_a_missing_runtime_is_a_sandbox_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(argv: list[str], **kwargs: Any) -> Any:
        raise FileNotFoundError("docker")

    monkeypatch.setattr(sandbox.subprocess, "run", fake_run)
    with pytest.raises(SandboxError, match="could not start"):
        sandbox.run_container([sandbox.DOCKER, "run"], "box-1", 1)
    with pytest.raises(SandboxError, match="could not reach"):
        sandbox.require_image("img")


def test_a_passing_draft_is_promoted_only_if_a_mutant_makes_it_fail(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    states = iter(["passed", "passed", "failed"])  # the draft, mutant 1, mutant 2

    def fake_run_draft(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"state": next(states), "passed": 1, "failed": 0, "detail": "", "seconds": 0.0}

    monkeypatch.setattr(sandbox, "run_draft", fake_run_draft)
    mutants = [
        {"file": "pkg/calc.py", "line": "return low", "mutated": "return high"},
        {"file": "pkg/calc.py", "line": "return min(value, high)", "mutated": "return value"},
    ]
    job = {"id": "j1", "repo": str(repo), "test": str(draft(tmp_path, PASSING)), "mutants": mutants}
    result = sandbox.check_job(job, Limits())
    assert [m["state"] for m in result["mutants"]] == ["survived", "killed"]
    assert result["promote"] is True


def test_a_failing_draft_is_never_tried_against_mutants(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs: list[int] = []

    def fake_run_draft(*args: Any, **kwargs: Any) -> dict[str, Any]:
        runs.append(1)
        return {"state": "failed", "passed": 0, "failed": 1, "detail": "", "seconds": 0.0}

    monkeypatch.setattr(sandbox, "run_draft", fake_run_draft)
    mutants = [{"file": "pkg/calc.py", "line": "return low", "mutated": "return high"}]
    job = {"id": "j1", "repo": str(repo), "test": str(draft(tmp_path, PASSING)), "mutants": mutants}
    result = sandbox.check_job(job, Limits())
    assert (len(runs), result["mutants"], result["promote"]) == (1, [], False)


def test_run_plan_refuses_a_bad_id_and_counts_states(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(SandboxError, match="must match"):
        sandbox.run_plan({"jobs": [{"id": "../x"}]})
    monkeypatch.setattr(sandbox, "require_image", lambda image: None)
    monkeypatch.setattr(
        sandbox,
        "check_job",
        lambda job, limits: {"id": job["id"], "state": job["s"], "promote": job["s"] == "passed"},
    )
    plan = {
        "jobs": [{"id": "a", "s": "passed"}, {"id": "b", "s": "failed"}, {"id": "c", "s": "passed"}]
    }
    summary = sandbox.run_plan(plan, workers=2)
    assert summary["counts"] == {"passed": 2, "failed": 1}
    assert summary["promoted"] == 2


def test_main_reports_a_sandbox_failure_with_exit_code_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"image": "missing", "jobs": []}), encoding="utf-8")

    def no_image(image: str) -> None:
        raise SandboxError("sandbox image 'missing' is not available")

    monkeypatch.setattr(sandbox, "require_image", no_image)
    assert sandbox.main([str(plan)]) == 2
    assert "not available" in capsys.readouterr().err


def test_the_ci_job_cannot_pass_by_skipping() -> None:
    """The container tests skip without an image; the CI job must turn that into a failure."""
    workflow = Path(".github/workflows/sandbox-ci.yml").read_text(encoding="utf-8")
    assert 'ALOS_SANDBOX_REQUIRED: "1"' in workflow
    assert "ALOS_SANDBOX_IMAGE: alos-sandbox:ci" in workflow
    assert "--tag alos-sandbox:ci" in workflow
    assert "-m docker" in workflow


# --- Container tests: the isolation claims, proven against a real runtime -------------


@needs_docker
@pytest.mark.docker
def test_the_sandbox_image_is_present() -> None:
    assert READY, f"ALOS_SANDBOX_IMAGE={IMAGE!r} is not a local image"


@needs_docker
@pytest.mark.docker
def test_a_sound_draft_passes_and_a_wrong_one_fails(repo: Path, tmp_path: Path) -> None:
    limits = Limits(image=IMAGE, timeout_s=60)
    good = sandbox.run_draft(repo, draft(tmp_path, PASSING), limits)
    assert (good["state"], good["passed"]) == ("passed", 2)
    wrong = PASSING.replace("== 3", "== 4")
    bad = sandbox.run_draft(repo, draft(tmp_path, wrong), limits)
    assert (bad["state"], bad["failed"]) == ("failed", 1)


@needs_docker
@pytest.mark.docker
def test_a_hostile_draft_is_blocked_on_every_route(repo: Path, tmp_path: Path) -> None:
    before = digest(repo)
    result = sandbox.run_draft(repo, draft(tmp_path, HOSTILE), Limits(image=IMAGE, timeout_s=60))
    assert (result["state"], result["passed"]) == ("passed", 5), result["detail"]
    assert digest(repo) == before


@needs_docker
@pytest.mark.docker
def test_a_destructive_draft_leaves_the_repository_untouched(repo: Path, tmp_path: Path) -> None:
    before = digest(repo)
    result = sandbox.run_draft(repo, draft(tmp_path, RUDE), Limits(image=IMAGE, timeout_s=60))
    assert result["state"] == "error"  # an outcome of the draft; the runner did not raise
    assert digest(repo) == before


@needs_docker
@pytest.mark.docker
def test_mutants_are_killed_or_survive_and_the_source_is_never_changed(
    repo: Path, tmp_path: Path
) -> None:
    before = digest(repo)
    mutants = [
        {"file": "pkg/calc.py", "line": "return min(value, high)", "mutated": "return value"},
        {"file": "pkg/calc.py", "line": "if value < low:", "mutated": "if value <= low:"},
        {"file": "pkg/calc.py", "line": "return nothing", "mutated": "return 1"},
    ]
    job = {"id": "j1", "repo": str(repo), "test": str(draft(tmp_path, PASSING)), "mutants": mutants}
    result = sandbox.check_job(job, Limits(image=IMAGE, timeout_s=60))
    assert result["state"] == "passed"
    assert [m["state"] for m in result["mutants"]] == ["killed", "survived", "not_found"]
    assert result["promote"] is True
    assert digest(repo) == before


@needs_docker
@pytest.mark.docker
def test_a_draft_that_never_finishes_is_stopped_and_removed(repo: Path, tmp_path: Path) -> None:
    looping = "def test_spins():\n    while True:\n        pass\n"
    result = sandbox.run_draft(repo, draft(tmp_path, looping), Limits(image=IMAGE, timeout_s=8))
    assert result["state"] == "timeout"
    listed = subprocess.run(
        ["docker", "ps", "--filter", "name=alos-sandbox-", "--format", "{{.Names}}"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    assert listed.stdout.strip() == ""


@needs_docker
@pytest.mark.docker
def test_a_plan_runs_end_to_end_and_writes_results(repo: Path, tmp_path: Path) -> None:
    plan = {
        "image": IMAGE,
        "timeout_s": 60,
        "jobs": [{"id": "good", "repo": str(repo), "test": str(draft(tmp_path, PASSING))}],
    }
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(plan), encoding="utf-8")
    assert sandbox.main([str(plan_file), "--workers", "1"]) == 0
    summary = json.loads((tmp_path / "sandbox-results.json").read_text(encoding="utf-8"))
    assert summary["counts"] == {"passed": 1}
    assert summary["promoted"] == 0  # no mutants were planned, so nothing is promoted
