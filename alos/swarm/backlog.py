"""Multi-repository GitHub, SpecKit, and OpenSpec backlog harvester and hold-gated stager.

Spec: specs/037-backlog-staging-and-burn/spec.md (FR-3708, FR-3709)
ADR: ADR-0025 (Multi-Repo Backlog Harvester, Active-Use Hold Latch, and Artifact Burn Executor)
"""

from __future__ import annotations

import argparse
import importlib.resources
import json
import re
import shutil
import subprocess  # nosec B404
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from sqlalchemy import select

from alos.db.models import ComputeQueueJobModel
from alos.db.session import DatabaseManager
from alos.runtime import QueueHoldLatch, RuntimePaths, bootstrap_home
from alos.swarm.queue import StickyEpochQueue

DEFAULT_PERSONAL_REPOS: tuple[str, ...] = (
    "brandon-fox/alos",
    "brandon-fox/nectR",
    "brandon-fox/first-ade",
    "brandon-fox/vindicta-specs",
)

NOISE_LABELS = frozenset({"main-guard", "automated", "dependencies", "wontfix"})
NOISE_TITLE_TOKENS = (
    "[main guard]",
    "feature completion dashboard",
    "complexity report:",
    "spec gap analysis:",
    "python compatibility failure:",
    "main guardian:",
)
TIER_ORDER = {"fast_coder": 0, "reasoner": 1, "architect": 2, "embed": 3}
UNCHECKED_TASK_RE = re.compile(r"^\s*-\s*\[\s\]\s+(.+)$")
SAFE_ID_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _clean_id(raw: str) -> str:
    return SAFE_ID_RE.sub("-", raw.strip()).strip("-")[:110] or "backlog-item"


def load_bundled_backlog() -> list[dict[str, Any]]:
    """Load the package-bundled curated multi-repository backlog snapshot."""
    pkg = importlib.resources.files("alos.templates.backlog")
    raw = pkg.joinpath("personal_repos_backlog.json").read_text(encoding="utf-8")
    loaded: list[dict[str, Any]] = json.loads(raw)
    return loaded


def _classify_tier_and_minutes(text: str) -> tuple[str, str, float]:
    low = text.lower()
    if any(k in low for k in ("architect", "consensus", "signedtransaction", "bootstrap", "mcp")):
        return "issue_plan", "architect", 7.0
    if any(k in low for k in ("test", "bdd", "gherkin", "hypothesis", "coverage")):
        return "test_draft", "fast_coder", 3.5
    if any(k in low for k in ("review", "lint", "docstring", "pin ", "sha")):
        return "review_fix", "fast_coder", 3.0
    if any(k in low for k in ("spec", "audit", "gap", "schema", "invariant")):
        return "spec_audit", "reasoner", 4.5
    return "task_patch", "reasoner", 5.0


def harvest_local_spec_tasks(repo_slug: str, repo_root: Path) -> list[dict[str, Any]]:
    """Scan local ``specs/*/tasks.md`` and ``openspec/changes/*/tasks.md`` for unchecked items."""
    patterns = ("specs/*/tasks.md", "openspec/changes/*/tasks.md")
    short_repo = repo_slug.rsplit("/", maxsplit=1)[-1].lower()
    items: list[dict[str, Any]] = []
    for pat in patterns:
        for tasks_file in sorted(repo_root.glob(pat)):
            rel = tasks_file.relative_to(repo_root).as_posix()
            for idx, line in enumerate(tasks_file.read_text(encoding="utf-8").splitlines(), 1):
                match = UNCHECKED_TASK_RE.match(line)
                if not match:
                    continue
                desc = match.group(1).strip()
                wf, tier, est = _classify_tier_and_minutes(desc)
                slug_part = _clean_id(f"{short_repo}-{tasks_file.parent.name}-L{idx}")
                items.append(
                    {
                        "job_id": slug_part,
                        "repo_slug": repo_slug,
                        "workflow_type": wf,
                        "model_tier": tier,
                        "priority": 75,
                        "estimated_minutes": est,
                        "payload": {
                            "title": desc[:140],
                            "source_ref": f"{repo_slug}:{rel}#L{idx}",
                            "prompt": f"Complete unchecked specification task:\n{desc}",
                        },
                    }
                )
    return items


def _run_gh_json(args: list[str]) -> list[dict[str, Any]]:
    gh_bin = shutil.which("gh")
    if gh_bin is None:
        return []
    # Fixed argument list invoking resolved official gh CLI without shell expansion.
    proc = subprocess.run(  # noqa: S603  # nosec B603
        [gh_bin, *args], capture_output=True, text=True, timeout=30, check=False
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return []
    parsed: list[dict[str, Any]] = json.loads(proc.stdout)
    return parsed


def _is_noise_issue(issue: dict[str, Any]) -> bool:
    title_low = str(issue.get("title", "")).lower()
    if any(tok in title_low for tok in NOISE_TITLE_TOKENS):
        return True
    labels = {
        str(lbl.get("name", "")).lower()
        for lbl in (issue.get("labels") or [])
        if isinstance(lbl, dict)
    }
    return bool(labels & NOISE_LABELS)


def harvest_live_github_backlog(
    repos: Sequence[str] = DEFAULT_PERSONAL_REPOS,
    max_per_repo: int = 20,
) -> list[dict[str, Any]]:
    """Harvest actionable open GitHub issues across ``repos`` while dropping bot spam."""
    harvested: list[dict[str, Any]] = []
    for repo in repos:
        short = _clean_id(repo.rsplit("/", maxsplit=1)[-1].lower())
        issues = _run_gh_json(
            [
                "issue",
                "list",
                "-R",
                repo,
                "--state",
                "open",
                "--limit",
                "50",
                "--json",
                "number,title,labels,body",
            ]
        )
        kept = 0
        for issue in issues:
            if kept >= max_per_repo or _is_noise_issue(issue):
                continue
            num = int(issue["number"])
            title = str(issue.get("title", f"Issue #{num}")).strip()
            body = str(issue.get("body") or "").strip()[:1200]
            wf, tier, est = _classify_tier_and_minutes(f"{title} {body[:200]}")
            harvested.append(
                {
                    "job_id": f"gh-{short}-issue-{num}",
                    "repo_slug": repo,
                    "workflow_type": wf,
                    "model_tier": tier,
                    "priority": 80,
                    "estimated_minutes": est,
                    "payload": {
                        "title": f"#{num}: {title}"[:140],
                        "source_ref": f"{repo}#{num}",
                        "prompt": f"Issue #{num}: {title}\n\n{body}".strip(),
                    },
                }
            )
            kept += 1
    return harvested


def select_backlog_window(
    items: Sequence[dict[str, Any]],
    repos: Sequence[str] | None = None,
    target_minutes: float = 165.0,
) -> list[dict[str, Any]]:
    """Filter by repository, order for sticky-epoch efficiency, and cap by ``target_minutes``."""
    allowed = set(repos) if repos else None
    filtered = [i for i in items if allowed is None or str(i.get("repo_slug")) in allowed]
    ordered = sorted(
        filtered,
        key=lambda i: (
            -int(i.get("priority", 50)),
            TIER_ORDER.get(str(i.get("model_tier", "fast_coder")), 9),
            str(i.get("job_id", "")),
        ),
    )
    if target_minutes <= 0:
        return ordered
    selected: list[dict[str, Any]] = []
    acc = 0.0
    for item in ordered:
        est = float(item.get("estimated_minutes", 4.0))
        if selected and (acc + est) > target_minutes:
            continue
        selected.append(item)
        acc += est
    return sorted(
        selected,
        key=lambda i: (
            TIER_ORDER.get(str(i.get("model_tier", "fast_coder")), 9),
            -int(i.get("priority", 50)),
            str(i.get("job_id", "")),
        ),
    )


def summarize_backlog(items: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Compute counts and estimated burn minutes grouped by repository and model tier."""
    by_repo: dict[str, int] = {}
    by_tier: dict[str, int] = {}
    total_min = 0.0
    for item in items:
        repo = str(item.get("repo_slug", "unknown"))
        tier = str(item.get("model_tier", "fast_coder"))
        by_repo[repo] = by_repo.get(repo, 0) + 1
        by_tier[tier] = by_tier.get(tier, 0) + 1
        total_min += float(item.get("estimated_minutes", 4.0))
    return {
        "total_items": len(items),
        "estimated_minutes": round(total_min, 1),
        "estimated_hours": round(total_min / 60.0, 2),
        "by_repo": by_repo,
        "by_tier": by_tier,
    }


def _write_staged_manifest(
    paths: RuntimePaths, items: Sequence[dict[str, Any]], summary: dict[str, Any]
) -> Path:
    paths.results_dir.mkdir(parents=True, exist_ok=True)
    json_path = paths.results_dir / "staged_backlog.json"
    md_path = paths.results_dir / "staged_backlog.md"
    json_path.write_text(json.dumps(list(items), indent=2), encoding="utf-8")

    lines = [
        "# Staged Multi-Repository Queue Backlog",
        "",
        f"- **Total Tasks**: {summary['total_items']}",
        f"- **Estimated GPU Burn**: {summary['estimated_minutes']} min "
        f"({summary['estimated_hours']} hours)",
        f"- **By Tier**: `{json.dumps(summary['by_tier'])}`",
        f"- **By Repo**: `{json.dumps(summary['by_repo'])}`",
        "",
        "## Staged Execution Order (Sticky Model-Epoch Grouped)",
        "",
    ]
    for idx, item in enumerate(items, 1):
        title = str((item.get("payload") or {}).get("title") or item["job_id"])
        lines.append(
            f"{idx}. `[{item['model_tier']}]` **{item['repo_slug']}** — "
            f"`{item['job_id']}` ({item.get('estimated_minutes', 4.0)}m): {title}"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path


def stage_backlog(
    db_url: str,
    paths: RuntimePaths,
    items: Sequence[dict[str, Any]],
    hold_mode: str = "idle_gate",
    arm_after_idle_s: float = 300.0,
    worktree_repos: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Idempotently enqueue ``items`` into ``StickyEpochQueue`` and engage the hold latch."""
    bootstrap_home(home=paths.root, db_url=db_url)
    db = DatabaseManager(db_url=db_url)
    queue = StickyEpochQueue(db=db)
    with db.get_session() as session:
        existing_ids = set(session.scalars(select(ComputeQueueJobModel.job_id)))

    wt_map = worktree_repos or {}
    staged_ids: list[str] = []
    skipped = 0
    for item in items:
        jid = str(item["job_id"])
        if jid in existing_ids:
            skipped += 1
            continue
        repo = str(item.get("repo_slug", "brandon-fox/alos"))
        payload = dict(item.get("payload") or {})
        if repo in wt_map:
            payload["create_worktree_branch"] = True
            payload["local_repo_path"] = wt_map[repo]
        queue.enqueue(
            job_id=jid,
            repo_slug=repo,
            workflow_type=str(item.get("workflow_type", "task_patch")),
            model_tier=str(item.get("model_tier", "fast_coder")),
            priority=int(item.get("priority", 50)),
            requires_merge=bool(item.get("requires_merge", False)),
            allow_cloud_overflow=bool(item.get("allow_cloud_overflow", False)),
            payload=payload,
        )
        existing_ids.add(jid)
        staged_ids.append(jid)

    latch = QueueHoldLatch(paths.hold_file)
    hold_state: dict[str, Any] | None = None
    if hold_mode == "manual":
        hold_state = latch.engage_manual("staged backlog manual hold")
    elif hold_mode == "idle_gate":
        hold_state = latch.engage_idle_gate(
            min_idle_s=arm_after_idle_s, reason="staged backlog waiting for workstation idle"
        )

    summary = summarize_backlog(items)
    manifest_path = _write_staged_manifest(paths, items, summary)
    return {
        "staged_new": len(staged_ids),
        "skipped_existing": skipped,
        **summary,
        "hold": hold_state,
        "manifest_path": str(manifest_path),
    }


def register_backlog_parser(sub: Any) -> None:
    """Attach ``backlog {summary,build,stage}`` subcommands to the governor CLI parser."""
    bp = sub.add_parser("backlog", help="Build or stage multi-repository GitHub/SpecKit backlogs")
    bsub = bp.add_subparsers(dest="backlog_action", required=True)
    for name in ("summary", "build", "stage"):
        p = bsub.add_parser(name, help=f"{name.capitalize()} multi-repository backlog")
        p.add_argument("--live-gh", action="store_true", help="Refresh open issues via gh CLI")
        p.add_argument("--repos", nargs="*", default=None, help="Filter target owner/repo slugs")
        p.add_argument("--target-minutes", type=float, default=165.0, help="Target burn minutes")
        if name == "build":
            p.add_argument("--out", required=True, help="Destination JSON file path")
        if name == "stage":
            p.add_argument("--hold", action="store_true", help="Engage strict manual pause latch")
            p.add_argument("--no-hold", action="store_true", help="Do not engage a hold latch")
            p.add_argument("--arm-after-idle", type=float, default=300.0, help="Idle seconds gate")
            p.add_argument(
                "--worktree-repo",
                action="append",
                default=[],
                help="Optional repo_slug=local_path mapping for worktree branch drafts",
            )


def _parse_worktree_mappings(raw_entries: Sequence[str]) -> dict[str, str]:
    mappings: dict[str, str] = {}
    for entry in raw_entries:
        if "=" in entry:
            slug, local_path = entry.split("=", 1)
            mappings[slug.strip()] = local_path.strip()
    return mappings


def run_backlog_cli(args: argparse.Namespace, paths: RuntimePaths, db_url: str) -> int:
    """Execute ``alos backlog {summary,build,stage}`` CLI actions."""
    repos = tuple(args.repos) if args.repos else DEFAULT_PERSONAL_REPOS
    raw_items = list(load_bundled_backlog())
    if args.live_gh:
        seen = {str(i["job_id"]) for i in raw_items}
        for live_item in harvest_live_github_backlog(repos=repos):
            if str(live_item["job_id"]) not in seen:
                raw_items.append(live_item)
                seen.add(str(live_item["job_id"]))
    selected = select_backlog_window(
        raw_items, repos=args.repos, target_minutes=float(args.target_minutes)
    )
    if args.backlog_action == "summary":
        print(json.dumps(summarize_backlog(selected), indent=2))
        return 0
    if args.backlog_action == "build":
        out = Path(str(args.out))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(selected, indent=2), encoding="utf-8")
        print(
            json.dumps({"written": len(selected), "path": str(out), **summarize_backlog(selected)})
        )
        return 0
    hold_mode = "none" if args.no_hold else ("manual" if args.hold else "idle_gate")
    wt_map = _parse_worktree_mappings(args.worktree_repo)
    report = stage_backlog(
        db_url=db_url,
        paths=paths,
        items=selected,
        hold_mode=hold_mode,
        arm_after_idle_s=float(args.arm_after_idle),
        worktree_repos=wt_map,
    )
    print(json.dumps(report, indent=2))
    return 0
