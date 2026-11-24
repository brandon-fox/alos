#!/usr/bin/env python3
"""Automatic SSH-signed PR rebase and signature enforcement helper (Spec 033)."""

from __future__ import annotations

import argparse
import http.client
import json
import os
import shutil
import subprocess  # nosec B404 - invokes resolved git binary with list argv and shell=False
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

HOLD_LABELS = frozenset({"wip", "do-not-merge"})


@dataclass(frozen=True)
class RebaseResult:
    """Outcome of evaluating or rebasing a single PR branch."""

    head_branch: str
    status: str
    behind_before: bool
    unsigned_before: list[str]
    unsigned_after: list[str]
    detail: str = ""


def _clean_git_env() -> dict[str, str]:
    drop = {
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_COMMON_DIR",
        "GIT_PREFIX",
    }
    return {k: v for k, v in os.environ.items() if k not in drop}


def run_git(repo_dir: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Execute git safely without shell interpolation."""
    git_bin = shutil.which("git") or "git"
    # Invokes resolved git executable with explicit argv list and shell=False.
    return subprocess.run(  # noqa: S603  # nosec B603
        [git_bin, *args],
        cwd=repo_dir,
        env=_clean_git_env(),
        text=True,
        capture_output=True,
        check=check,
    )


def find_unsigned_commits(repo_dir: Path, base_ref: str, head_ref: str) -> list[str]:
    """List commit SHAs in base_ref..head_ref that lack a gpgsig header."""
    proc = run_git(repo_dir, "log", f"{base_ref}..{head_ref}", "--format=%H", check=False)
    if proc.returncode != 0:
        return []
    return [
        sha
        for sha in (line.strip() for line in proc.stdout.splitlines() if line.strip())
        if not any(
            line.startswith("gpgsig")
            for line in run_git(
                repo_dir, "cat-file", "commit", sha, check=False
            ).stdout.splitlines()
        )
    ]


def is_behind(repo_dir: Path, base_ref: str, head_ref: str) -> bool:
    """Return True when base_ref is not an ancestor of head_ref."""
    return (
        run_git(repo_dir, "merge-base", "--is-ancestor", base_ref, head_ref, check=False).returncode
        != 0
    )


def rebase_and_sign_branch(
    repo_dir: Path, base_branch: str, head_branch: str, signing_configured: bool, push: bool = True
) -> RebaseResult:
    """Rebase head_branch onto origin/base_branch with signed commits if behind or unsigned."""
    run_git(repo_dir, "fetch", "origin", base_branch, head_branch)
    base_ref, head_ref = f"origin/{base_branch}", f"origin/{head_branch}"
    behind = is_behind(repo_dir, base_ref, head_ref)
    unsigned = find_unsigned_commits(repo_dir, base_ref, head_ref)
    if not behind and not unsigned:
        return RebaseResult(head_branch, "up_to_date", False, [], [], "Up to date and signed.")
    if not signing_configured:
        return RebaseResult(
            head_branch,
            "missing_signing_key",
            behind,
            unsigned,
            unsigned,
            "COMMIT_SIGNING_KEY missing.",
        )
    run_git(repo_dir, "checkout", "-B", head_branch, head_ref)
    rb = run_git(repo_dir, "rebase", "--force-rebase", base_ref, check=False)
    if rb.returncode != 0:
        run_git(repo_dir, "rebase", "--abort", check=False)
        return RebaseResult(
            head_branch, "conflict", behind, unsigned, unsigned, (rb.stderr or rb.stdout).strip()
        )
    unsigned_after = find_unsigned_commits(repo_dir, base_ref, "HEAD")
    if unsigned_after:
        return RebaseResult(
            head_branch,
            "unsigned_after_rebase",
            behind,
            unsigned,
            unsigned_after,
            "Unsigned after rebase.",
        )
    if push:
        ps = run_git(
            repo_dir, "push", "--force-with-lease", "origin", f"HEAD:{head_branch}", check=False
        )
        if ps.returncode != 0:
            return RebaseResult(
                head_branch, "push_failed", behind, unsigned, [], (ps.stderr or ps.stdout).strip()
            )
    return RebaseResult(head_branch, "rebased", behind, unsigned, [], "Rebased and signed.")


def rank_queue_candidates(prs: list[dict[str, Any]], repo_full_name: str) -> list[dict[str, Any]]:
    """Filter and prioritize open PRs for serialized queue rebasing."""
    eligible = [
        pr
        for pr in prs
        if ((pr.get("head") or {}).get("repo") or {}).get("full_name") == repo_full_name
        and not ({str(lbl.get("name", "")) for lbl in (pr.get("labels") or [])} & HOLD_LABELS)
        and pr.get("mergeable_state") != "dirty"
    ]
    eligible.sort(
        key=lambda pr: (
            not bool(pr.get("auto_merge")),
            bool(pr.get("draft")),
            int(pr.get("number", 0)),
        )
    )
    return eligible


def _github_get_json(path: str, headers: dict[str, str]) -> Any:
    conn = http.client.HTTPSConnection("api.github.com", timeout=20)
    try:
        conn.request("GET", path, headers=headers)
        resp = conn.getresponse()
        body = resp.read().decode("utf-8")
        if resp.status >= 400:
            raise RuntimeError(f"GitHub API {path} HTTP {resp.status}: {body[:200]}")
        return json.loads(body)
    finally:
        conn.close()


def _fetch_open_prs(repo_full_name: str, base_branch: str, token: str) -> list[dict[str, Any]]:
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "alos-signed-pr-rebase",
    }
    list_path = (
        f"/repos/{repo_full_name}/pulls"
        f"?state=open&base={base_branch}&sort=created&direction=asc&per_page=30"
    )
    detailed: list[dict[str, Any]] = []
    for summary in _github_get_json(list_path, headers):
        try:
            detailed.append(
                _github_get_json(f"/repos/{repo_full_name}/pulls/{summary['number']}", headers)
            )
        except (OSError, RuntimeError, json.JSONDecodeError):
            detailed.append(summary)
    return detailed


def _write_github_output(result: RebaseResult, pr_number: int | None = None) -> None:
    if not (output_path := os.environ.get("GITHUB_OUTPUT")):
        return
    with Path(output_path).open("a", encoding="utf-8") as fh:
        fh.write(f"status={result.status}\nhead_branch={result.head_branch}\n")
        if pr_number is not None:
            fh.write(f"pr_number={pr_number}\n")


def _run_queue_mode(repo_dir: Path, base_branch: str, signing_configured: bool, push: bool) -> int:
    repo_full_name, token = os.environ.get("GITHUB_REPOSITORY", ""), os.environ.get("GH_TOKEN", "")
    if not repo_full_name or not token:
        print("GITHUB_REPOSITORY and GH_TOKEN are required in queue mode.", file=sys.stderr)
        return 1
    candidates = rank_queue_candidates(
        _fetch_open_prs(repo_full_name, base_branch, token), repo_full_name
    )
    last = RebaseResult("", "up_to_date" if candidates else "no_candidates", False, [], [], "")
    for pr in candidates:
        pr_num = int(pr["number"])
        res = rebase_and_sign_branch(
            repo_dir, base_branch, str(pr["head"]["ref"]), signing_configured, push
        )
        print(json.dumps({"pr_number": pr_num, **asdict(res)}))
        if res.status in {"rebased", "missing_signing_key"}:
            _write_github_output(res, pr_number=pr_num)
            return 1 if res.status == "missing_signing_key" else 0
        last = res
    _write_github_output(last)
    print(json.dumps(asdict(last)))
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for single-PR and queue signed rebasing."""
    parser = argparse.ArgumentParser(description="Automatic SSH-signed PR rebase helper")
    parser.add_argument("--mode", choices=["single", "queue"], required=True)
    parser.add_argument("--repo-dir", type=Path, default=Path("."))
    parser.add_argument("--base-branch", default="main")
    parser.add_argument("--head-branch", default="")
    parser.add_argument("--signing-configured", default="false")
    parser.add_argument("--no-push", action="store_true")
    args = parser.parse_args(argv)
    signing_configured = str(args.signing_configured).lower() == "true"
    if args.mode == "single":
        if not args.head_branch:
            print("--head-branch is required in single mode.", file=sys.stderr)
            return 1
        res = rebase_and_sign_branch(
            args.repo_dir, args.base_branch, args.head_branch, signing_configured, not args.no_push
        )
        _write_github_output(res)
        print(json.dumps(asdict(res)))
        return (
            1
            if res.status in {"missing_signing_key", "unsigned_after_rebase", "push_failed"}
            else 0
        )
    return _run_queue_mode(args.repo_dir, args.base_branch, signing_configured, not args.no_push)


if __name__ == "__main__":
    raise SystemExit(main())
