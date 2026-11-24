"""BDD step definitions for automatic_signed_pr_rebase.feature (Spec 033)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pytest_bdd import given, parsers, scenarios, then, when

from tests.test_signed_pr_rebase import (
    commit_branch,
    git,
    load_rebase_module,
    setup_ssh_signing_repo,
)

scenarios("../features/automatic_signed_pr_rebase.feature")


@given(parsers.parse('the GitHub workflow "{wf_path}"'))
def step_load_workflow(bdd_context: dict[str, Any], wf_path: str) -> None:
    bdd_context["wf_text"] = Path(wf_path).read_text(encoding="utf-8")


@then("it marks non-hold draft pull requests ready for review before enabling auto-merge")
def step_check_draft_ready(bdd_context: dict[str, Any]) -> None:
    assert "'ready'" in bdd_context["wf_text"] and "pr.draft" in bdd_context["wf_text"]


@then("it enables squash auto-merge for human, Dependabot, and bot pull requests")
def step_check_universal_automerge(bdd_context: dict[str, Any]) -> None:
    t = bdd_context["wf_text"]
    assert "github.actor != 'dependabot[bot]'" not in t
    assert "github.actor != 'github-actions[bot]'" not in t
    assert "--auto" in t and "--squash" in t


@then('it skips pull requests labeled "wip" or "do-not-merge"')
def step_check_hold_labels(bdd_context: dict[str, Any]) -> None:
    assert "wip" in bdd_context["wf_text"] and "do-not-merge" in bdd_context["wf_text"]


def _setup_case(ctx: dict[str, Any], tmp_path: Path, conflict: bool) -> None:
    _r, work, runner = setup_ssh_signing_repo(tmp_path)
    tgt, mtgt = ("README.md", "README.md") if conflict else ("feat.txt", "main.txt")
    before = commit_branch(work, "feat/bdd", tgt, "feature\n", signed=False)
    git(work, "checkout", "main")
    (work / mtgt).write_text("main\n", encoding="utf-8")
    git(work, "add", mtgt)
    git(work, "commit", "-m", "chore: advance main")
    git(work, "push", "origin", "main")
    ctx.update({"work": work, "runner": runner, "before_sha": before})


@given("a bare remote repository with main advanced ahead of a feature branch")
def step_behind(bdd_context: dict[str, Any], tmp_path: Path) -> None:
    _setup_case(bdd_context, tmp_path, conflict=False)


@given("the feature branch contains an unsigned commit")
def step_unsigned_before(bdd_context: dict[str, Any]) -> None:
    assert load_rebase_module().find_unsigned_commits(
        bdd_context["work"], "origin/main", "origin/feat/bdd"
    )


@given("a bare remote repository where main and the feature branch modify the same line")
def step_conflict(bdd_context: dict[str, Any], tmp_path: Path) -> None:
    _setup_case(bdd_context, tmp_path, conflict=True)


@when("signed_pr_rebase executes in single mode with an ephemeral SSH signing key")
def step_run_single(bdd_context: dict[str, Any]) -> None:
    bdd_context["result"] = load_rebase_module().rebase_and_sign_branch(
        bdd_context["runner"], "main", "feat/bdd", True, True
    )


@then("the feature branch is rebased onto origin main")
def step_rebased(bdd_context: dict[str, Any]) -> None:
    assert bdd_context["result"].status == "rebased"
    git(bdd_context["work"], "fetch", "origin")
    rc = git(
        bdd_context["work"],
        "merge-base",
        "--is-ancestor",
        "origin/main",
        "origin/feat/bdd",
        check=False,
    ).returncode
    assert rc == 0


@then("every commit between origin main and HEAD carries a gpgsig header")
def step_all_signed(bdd_context: dict[str, Any]) -> None:
    assert not load_rebase_module().find_unsigned_commits(
        bdd_context["work"], "origin/main", "origin/feat/bdd"
    )


@then(parsers.parse('the rebase reports status "{expected}"'))
def step_status(bdd_context: dict[str, Any], expected: str) -> None:
    assert bdd_context["result"].status == expected


@then("the feature branch tip remains unchanged without leftover rebase state")
def step_conflict_clean(bdd_context: dict[str, Any]) -> None:
    assert not (bdd_context["runner"] / ".git" / "REBASE_HEAD").exists()
    git(bdd_context["work"], "fetch", "origin")
    assert (
        git(bdd_context["work"], "rev-parse", "origin/feat/bdd").stdout.strip()
        == bdd_context["before_sha"]
    )


@given(
    "open pull requests where the oldest behind PR has a merge conflict "
    "and the second behind PR is clean"
)
def step_queue_prs(bdd_context: dict[str, Any], tmp_path: Path) -> None:
    _r, work, runner = setup_ssh_signing_repo(tmp_path)
    commit_branch(work, "feat/pr1", "README.md", "pr1\n")
    git(work, "checkout", "main")
    commit_branch(work, "feat/pr2", "pr2.txt", "pr2\n", signed=False)
    git(work, "checkout", "main")
    (work / "README.md").write_text("main\n", encoding="utf-8")
    git(work, "add", "README.md")
    git(work, "commit", "-m", "chore: conflict")
    git(work, "push", "origin", "main")
    prs = [
        {
            "number": n,
            "draft": False,
            "labels": [],
            "auto_merge": True,
            "mergeable_state": "behind",
            "head": {"ref": r, "repo": {"full_name": "brandon-fox/alos"}},
        }
        for n, r in ((1, "feat/pr1"), (2, "feat/pr2"))
    ]
    bdd_context.update({"q_runner": runner, "q_prs": prs})


@when("signed_pr_rebase selects and rebases the next queue candidate")
def step_run_queue(bdd_context: dict[str, Any]) -> None:
    mod = load_rebase_module()
    results = []
    for pr in mod.rank_queue_candidates(bdd_context["q_prs"], "brandon-fox/alos"):
        res = mod.rebase_and_sign_branch(
            bdd_context["q_runner"], "main", pr["head"]["ref"], True, True
        )
        results.append((pr["number"], res))
        if res.status == "rebased":
            break
    bdd_context["q_results"] = results


@then("the conflicting PR is skipped and the clean PR is rebased with signed commits")
def step_queue_verified(bdd_context: dict[str, Any]) -> None:
    res = bdd_context["q_results"]
    assert res[0][0] == 1 and res[0][1].status == "conflict"
    assert res[1][0] == 2 and res[1][1].status == "rebased" and not res[1][1].unsigned_after
