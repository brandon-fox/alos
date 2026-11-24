"""Tests and shared Git/SSH-signing helpers for .github/scripts/signed_pr_rebase.py (Spec 033)."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

SCRIPT_PATH = Path(".github/scripts/signed_pr_rebase.py")


def load_rebase_module() -> Any:
    """Load .github/scripts/signed_pr_rebase.py dynamically."""
    spec = importlib.util.spec_from_file_location("signed_pr_rebase", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["signed_pr_rebase"] = module
    spec.loader.exec_module(module)
    return module


def git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run git in cwd using resolved executable path."""
    git_bin = shutil.which("git") or "git"
    env = load_rebase_module()._clean_git_env()
    # Invokes resolved git executable with explicit argv list in isolated temp repo.
    return subprocess.run(  # noqa: S603
        [git_bin, *args], cwd=cwd, env=env, text=True, capture_output=True, check=check
    )


def setup_ssh_signing_repo(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create bare remote, work clone, and runner clone configured with an ephemeral SSH key."""
    ssh_keygen = shutil.which("ssh-keygen")
    if not ssh_keygen:
        pytest.skip("ssh-keygen not available")
    key_path = tmp_path / "test_signing_key"
    # Invokes resolved ssh-keygen executable to generate ephemeral test key in tmp_path.
    subprocess.run(  # noqa: S603
        [ssh_keygen, "-t", "ed25519", "-N", "", "-f", str(key_path), "-q"],
        check=True,
        capture_output=True,
    )
    pub = key_path.with_suffix(".pub")
    remote, work, runner = tmp_path / "remote.git", tmp_path / "work", tmp_path / "runner"
    git(tmp_path, "init", "--bare", "-b", "main", str(remote))
    git(tmp_path, "clone", str(remote), str(work))
    cfg = (
        ("user.name", "Test"),
        ("user.email", "t@example.com"),
        ("gpg.format", "ssh"),
        ("user.signingkey", str(pub)),
        ("commit.gpgsign", "true"),
    )
    for k, v in cfg:
        git(work, "config", k, v)
    (work / "README.md").write_text("# ALOS\n", encoding="utf-8")
    git(work, "add", "README.md")
    git(work, "commit", "-m", "chore: initial")
    git(work, "push", "-u", "origin", "main")
    git(tmp_path, "clone", str(remote), str(runner))
    for k, v in cfg:
        git(runner, "config", k, v)
    return remote, work, runner


def commit_branch(
    work: Path, branch: str, filename: str, content: str, *, signed: bool = True
) -> str:
    """Create branch from HEAD, commit filename, push, and return SHA."""
    git(work, "checkout", "-b", branch)
    (work / filename).write_text(content, encoding="utf-8")
    git(work, "add", filename)
    cmd = ["commit", "-m", f"feat: {branch}"]
    git(work, *(["-c", "commit.gpgsign=false", *cmd] if not signed else cmd))
    git(work, "push", "-u", "origin", branch)
    return git(work, "rev-parse", "HEAD").stdout.strip()


def test_resign_and_missing_key_behaviors(tmp_path: Path) -> None:
    """Up-to-date unsigned PR is re-signed; missing signing key fails closed."""
    mod = load_rebase_module()
    _r, work, runner = setup_ssh_signing_repo(tmp_path)
    commit_branch(work, "feat/u", "u.txt", "u\n", signed=False)
    assert (
        mod.rebase_and_sign_branch(runner, "main", "feat/u", False, True).status
        == "missing_signing_key"
    )
    assert mod.rebase_and_sign_branch(runner, "main", "feat/u", True, True).status == "rebased"
    assert mod.rebase_and_sign_branch(runner, "main", "feat/u", True, True).status == "up_to_date"


def test_select_queue_candidates_prioritizes_automerge_and_skips_dirty() -> None:
    """Queue ordering prioritizes auto_merge PRs, skips holds/forks/dirty, and returns eligible."""
    mod = load_rebase_module()
    prs = [
        {
            "number": 10,
            "draft": False,
            "labels": [{"name": "wip"}],
            "auto_merge": None,
            "mergeable_state": "behind",
            "head": {"ref": "a", "repo": {"full_name": "brandon-fox/alos"}},
        },
        {
            "number": 11,
            "draft": False,
            "labels": [],
            "auto_merge": {"merge_method": "squash"},
            "mergeable_state": "dirty",
            "head": {"ref": "b", "repo": {"full_name": "brandon-fox/alos"}},
        },
        {
            "number": 12,
            "draft": True,
            "labels": [],
            "auto_merge": None,
            "mergeable_state": "behind",
            "head": {"ref": "c", "repo": {"full_name": "brandon-fox/alos"}},
        },
        {
            "number": 13,
            "draft": False,
            "labels": [],
            "auto_merge": {"merge_method": "squash"},
            "mergeable_state": "behind",
            "head": {"ref": "d", "repo": {"full_name": "brandon-fox/alos"}},
        },
    ]
    assert [p["number"] for p in mod.rank_queue_candidates(prs, "brandon-fox/alos")] == [13, 12]
