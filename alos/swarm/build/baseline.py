"""Per-attempt worktrees, diff application and the test step of the build baseline.

The test step here runs on the host inside a throwaway worktree. Spec 039 PR-5 moves it
into the spec 030 sandbox; ``executor.run_build`` takes the runner as a parameter so that
swap changes nothing else.

Spec: specs/039-self-correcting-build-executor/spec.md (FR-3902, FR-3904, FR-3906)
"""

from __future__ import annotations

import os
import shutil
import subprocess  # nosec B404
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

TAIL_LINES = 40
TAIL_CHARS = 2400
DEFAULT_TEST_COMMAND: tuple[str, ...] = (
    sys.executable,
    "-m",
    "pytest",
    "-q",
    "-x",
    "-p",
    "no:cacheprovider",
)
_GIT_ENV_DROP = frozenset(
    {
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_COMMON_DIR",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_PREFIX",
    }
)


class BuildError(RuntimeError):
    """The build environment failed; the model's change is not to blame."""


@dataclass(frozen=True)
class StepResult:
    name: str
    passed: bool
    output: str


def trim_output(text: str) -> str:
    """Keep the tail of a tool's output, which is where failures are reported."""
    lines = text.strip().splitlines()[-TAIL_LINES:]
    return "\n".join(lines)[-TAIL_CHARS:]


def git(repo: Path, *args: str, stdin: str | None = None, timeout: float = 60.0) -> tuple[int, str]:
    """Run git in ``repo`` and return ``(exit code, combined output)``."""
    git_bin = shutil.which("git")
    if git_bin is None:
        raise BuildError("git is not installed")
    env = {k: v for k, v in os.environ.items() if k not in _GIT_ENV_DROP}
    # Fixed argument vector with the resolved git binary; no shell.
    res = subprocess.run(  # noqa: S603  # nosec B603
        [git_bin, "-C", str(repo), *args],
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=env,
        check=False,
    )
    return res.returncode, res.stdout + res.stderr


def add_worktree(repo: Path, folder: Path, branch: str, base: str = "HEAD") -> None:
    """Create a worktree on a fresh branch at ``base``."""
    folder.parent.mkdir(parents=True, exist_ok=True)
    code, out = git(repo, "worktree", "add", "-B", branch, str(folder), base)
    if code != 0:
        raise BuildError(f"worktree add failed: {trim_output(out)}")


def remove_worktree(repo: Path, folder: Path, branch: str) -> None:
    """Remove a worktree and its branch; missing pieces are fine."""
    git(repo, "worktree", "remove", "--force", str(folder))
    shutil.rmtree(folder, ignore_errors=True)
    git(repo, "worktree", "prune")
    git(repo, "branch", "-D", branch)


def apply_diff(folder: Path, diff: str) -> StepResult:
    """Apply a unified diff all-or-nothing; hunk line counts are recomputed for model diffs."""
    text = diff if diff.endswith("\n") else diff + "\n"
    code, out = git(folder, "apply", "--recount", "--whitespace=nowarn", stdin=text)
    return StepResult("apply", code == 0, trim_output(out))


def host_tests(folder: Path, command: Sequence[str], timeout_s: float) -> StepResult:
    """Run the test command in ``folder`` on the host (replaced by the sandbox in PR-5)."""
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        # Command comes from the queue item's own payload, not from model output.
        res = subprocess.run(  # noqa: S603  # nosec B603
            list(command),
            cwd=folder,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return StepResult("tests", False, f"timed out after {int(timeout_s)} s")
    except OSError as exc:
        raise BuildError(f"test command could not start: {exc}") from exc
    return StepResult("tests", res.returncode == 0, trim_output(res.stdout + res.stderr))
