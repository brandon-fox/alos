"""Unit and integration tests for Spec 037 MultiRepoBacklogBuilder and backlog CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from alos.runtime import QueueHoldLatch, RuntimePaths
from alos.swarm.backlog import (
    harvest_live_github_backlog,
    harvest_local_spec_tasks,
    load_bundled_backlog,
    select_backlog_window,
    stage_backlog,
    summarize_backlog,
)
from alos.swarm.queue import main as queue_main


def test_bundled_backlog_covers_four_personal_repos_and_two_plus_hours() -> None:
    """FR-3708, FR-3709: Bundled snapshot spans all 4 active repos and >= 140 minutes."""
    items = load_bundled_backlog()
    assert len(items) >= 35
    summary = summarize_backlog(items)
    assert set(summary["by_repo"]) == {
        "brandon-fox/alos",
        "brandon-fox/nectR",
        "brandon-fox/first-ade",
        "brandon-fox/vindicta-specs",
    }
    assert summary["estimated_minutes"] >= 140.0
    assert set(summary["by_tier"]).issubset({"fast_coder", "reasoner", "architect", "embed"})


def test_stage_backlog_is_idempotent_and_engages_hold_latch(tmp_path: Path) -> None:
    """FR-3701, FR-3702, FR-3708: Staging inserts once, skips duplicates, and holds execution."""
    home = tmp_path / "alos_home"
    paths = RuntimePaths.resolve(home)
    db_url = paths.resolve_db_url()
    items = select_backlog_window(load_bundled_backlog(), target_minutes=150.0)

    first = stage_backlog(
        db_url=db_url,
        paths=paths,
        items=items,
        hold_mode="idle_gate",
        arm_after_idle_s=300.0,
    )
    assert first["staged_new"] == len(items)
    assert first["skipped_existing"] == 0
    assert first["estimated_minutes"] >= 120.0
    assert Path(first["manifest_path"]).exists()
    assert QueueHoldLatch(paths.hold_file).evaluate(user_idle_seconds=10.0).held is True

    # Re-staging same items is 100% idempotent
    second = stage_backlog(
        db_url=db_url, paths=paths, items=items, hold_mode="manual", arm_after_idle_s=0.0
    )
    assert second["staged_new"] == 0
    assert second["skipped_existing"] == len(items)
    assert QueueHoldLatch(paths.hold_file).read()["mode"] == "manual"  # type: ignore[index]


def test_live_gh_harvester_filters_bot_noise_and_local_specs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-3708: Live harvester drops main-guard/automated bot noise and parses tasks.md."""
    spec_dir = tmp_path / "specs" / "037-demo"
    spec_dir.mkdir(parents=True)
    (spec_dir / "tasks.md").write_text(
        "- [x] T001 Done item\n- [ ] T002 [US1] Implement adapter in alos/foo.py\n",
        encoding="utf-8",
    )
    local_items = harvest_local_spec_tasks("brandon-fox/alos", tmp_path)
    assert len(local_items) == 1
    assert "T002" in local_items[0]["payload"]["title"]

    fake_issues = [
        {
            "number": 120,
            "title": "[Main Guard] Warnings or Missing Tests Detected on main",
            "labels": [{"name": "main-guard"}],
            "body": "bot warning",
        },
        {
            "number": 161,
            "title": "Review comments deferred from #153",
            "labels": [],
            "body": "Pin action SHA in sonar-llm-fix.yml",
        },
    ]

    def _fake_gh_json(args: list[str]) -> list[dict[str, object]]:
        return fake_issues if "issue" in args else []

    monkeypatch.setattr("alos.swarm.backlog._run_gh_json", _fake_gh_json)
    harvested = harvest_live_github_backlog(["brandon-fox/first-ade"])
    assert len(harvested) == 1
    assert harvested[0]["job_id"] == "gh-first-ade-issue-161"


def test_cli_backlog_summary_build_and_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-3708, FR-3709: CLI backlog summary, build, --live-gh, and stage --worktree-repo."""
    from alos.swarm.backlog import _run_gh_json

    monkeypatch.setattr("shutil.which", lambda _cmd: None)
    assert _run_gh_json(["issue", "list"]) == []
    assert len(select_backlog_window(load_bundled_backlog(), target_minutes=0.0)) >= 35

    monkeypatch.setattr(
        "alos.swarm.backlog.harvest_live_github_backlog",
        lambda **_kw: [
            {
                "job_id": "gh-live-extra-1",
                "repo_slug": "brandon-fox/alos",
                "workflow_type": "spec_audit",
                "model_tier": "reasoner",
                "priority": 99,
                "estimated_minutes": 4.0,
                "payload": {"title": "Extra live audit"},
            }
        ],
    )
    home = tmp_path / "cli_home"
    out_json = tmp_path / "built.json"
    assert queue_main(["--home", str(home), "--mock", "backlog", "summary", "--live-gh"]) == 0
    assert (
        queue_main(
            [
                "--home",
                str(home),
                "--mock",
                "backlog",
                "build",
                "--target-minutes",
                "90",
                "--out",
                str(out_json),
            ]
        )
        == 0
    )
    built = json.loads(out_json.read_text(encoding="utf-8"))
    assert len(built) >= 15
    assert (
        queue_main(
            [
                "--home",
                str(home),
                "--mock",
                "backlog",
                "stage",
                "--live-gh",
                "--target-minutes",
                "130",
                "--hold",
                "--worktree-repo",
                f"brandon-fox/alos={tmp_path}",
            ]
        )
        == 0
    )
    paths = RuntimePaths.resolve(home)
    assert paths.hold_file.exists()
