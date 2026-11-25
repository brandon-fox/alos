"""Declarative GitHub repository settings, branch/tag ruleset sync, and collaborator sentinel.

Spec: specs/038-enterprise-cicd-pipeline/spec.md (FR-010)
ADR: ADR-0026
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess  # nosec B404
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RULESETS_DIR = REPO_ROOT / ".github" / "rulesets"


def load_local_manifests(rulesets_dir: Path = DEFAULT_RULESETS_DIR) -> dict[str, Any]:
    """Load declarative repo-settings, main-branch, and release-tags JSON manifests."""
    return {
        "repo_settings": json.loads((rulesets_dir / "repo-settings.json").read_text("utf-8")),
        "main_branch": json.loads((rulesets_dir / "main-branch.json").read_text("utf-8")),
        "release_tags": json.loads((rulesets_dir / "release-tags.json").read_text("utf-8")),
    }


def _gh_api(endpoint: str, method: str = "GET", payload: dict[str, Any] | None = None) -> Any:
    """Invoke gh api with optional JSON stdin payload and return parsed JSON."""
    gh = shutil.which("gh") or "gh"
    cmd = [gh, "api", endpoint, "-X", method]
    stdin_text = None
    if payload is not None:
        cmd.extend(["--input", "-"])
        stdin_text = json.dumps(payload)
    proc = subprocess.run(  # noqa: S603  # nosec B603 - fixed gh CLI invocation without shell
        cmd, input=stdin_text, capture_output=True, text=True, check=False
    )
    if proc.returncode != 0:
        raise RuntimeError(f"gh api {method} {endpoint} failed: {proc.stderr.strip()}")
    return json.loads(proc.stdout) if proc.stdout.strip() else {}


def fetch_live_state(repo_slug: str) -> dict[str, Any]:
    """Fetch live repo settings, Actions permissions, rulesets, and human collaborators."""
    rulesets_summary = _gh_api(f"repos/{repo_slug}/rulesets")
    rulesets_full = {
        rs["name"]: _gh_api(f"repos/{repo_slug}/rulesets/{rs['id']}") for rs in rulesets_summary
    }
    return {
        "repo": _gh_api(f"repos/{repo_slug}"),
        "actions": _gh_api(f"repos/{repo_slug}/actions/permissions"),
        "workflow": _gh_api(f"repos/{repo_slug}/actions/permissions/workflow"),
        "rulesets": rulesets_full,
        "collaborators": _gh_api(f"repos/{repo_slug}/collaborators"),
    }


def _subset_mismatch(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    """Return keys where actual differs from expected."""
    return {
        k: {"expected": v, "actual": actual.get(k)}
        for k, v in expected.items()
        if actual.get(k) != v
    }


def _ruleset_drift(expected: dict[str, Any], live_rs: dict[str, Any]) -> dict[str, Any]:
    """Compare declarative ruleset rules and enforcement against live GitHub ruleset."""
    diff: dict[str, Any] = {}
    if live_rs.get("enforcement") != expected["enforcement"]:
        diff["enforcement"] = {
            "expected": expected["enforcement"],
            "actual": live_rs.get("enforcement"),
        }
    exp_rules = {r["type"]: r.get("parameters", {}) for r in expected.get("rules", [])}
    act_rules = {r["type"]: r.get("parameters", {}) for r in live_rs.get("rules", [])}
    if set(exp_rules) != set(act_rules):
        diff["rule_types"] = {"expected": sorted(exp_rules), "actual": sorted(act_rules)}
    for rtype, exp_params in exp_rules.items():
        if rtype in act_rules and exp_params:
            sub = _subset_mismatch(exp_params, act_rules[rtype])
            if sub:
                diff[f"rule:{rtype}"] = sub
    return diff


def compute_drift(bundle: dict[str, Any], live: dict[str, Any]) -> list[dict[str, Any]]:
    """Compute structured governance drift items and check >1 collaborator sentinel."""
    findings: list[dict[str, Any]] = []
    sections = (
        ("repo_settings", "repo"),
        ("actions_permissions", "actions"),
        ("workflow_permissions", "workflow"),
    )
    for section, key in sections:
        diff = _subset_mismatch(bundle["repo_settings"][key], live.get(key, {}))
        if diff:
            findings.append({"category": section, "diff": diff})

    for manifest_key in ("main_branch", "release_tags"):
        spec = bundle[manifest_key]
        name = spec["name"]
        live_rs = live.get("rulesets", {}).get(name)
        if not live_rs:
            findings.append(
                {"category": f"missing_ruleset:{name}", "diff": {"expected": "present"}}
            )
            continue
        rs_diff = _ruleset_drift(spec, live_rs)
        if rs_diff:
            findings.append({"category": f"ruleset:{name}", "diff": rs_diff})

    humans = [c for c in live.get("collaborators", []) if c.get("type") == "User"]
    pr_rule: dict[str, Any] = next(
        (r for r in bundle["main_branch"]["rules"] if r["type"] == "pull_request"), {}
    )
    req_reviews = pr_rule.get("parameters", {}).get("required_approving_review_count", 0)
    if len(humans) > 1 and req_reviews < 1:
        findings.append(
            {
                "category": "collaborator_review_escalation_needed",
                "diff": {
                    "human_collaborators": [u.get("login") for u in humans],
                    "action": (
                        "Raise required_approving_review_count to 1 "
                        "and require_code_owner_review to true"
                    ),
                },
            }
        )
    return findings


def verify_main_checks_exist(main_spec: dict[str, Any], observed_check_names: set[str]) -> None:
    """Verify required status checks have reported on main before applying ruleset updates."""
    for rule in main_spec.get("rules", []):
        if rule.get("type") == "required_status_checks":
            reqs = {c["context"] for c in rule["parameters"]["required_status_checks"]}
            missing = sorted(reqs - observed_check_names)
            if missing:
                joined = ", ".join(missing)
                raise RuntimeError(
                    f"Refusing to apply main ruleset before check(s) report on main: {joined}"
                )


def apply_governance(repo_slug: str, bundle: dict[str, Any], force: bool = False) -> None:
    """Apply declarative repository settings and branch/tag rulesets idempotently."""
    if not force:
        runs = _gh_api(f"repos/{repo_slug}/commits/main/check-runs").get("check_runs", [])
        verify_main_checks_exist(bundle["main_branch"], {r["name"] for r in runs})

    _gh_api(f"repos/{repo_slug}", method="PATCH", payload=bundle["repo_settings"]["repo"])
    _gh_api(
        f"repos/{repo_slug}/actions/permissions",
        method="PUT",
        payload=bundle["repo_settings"]["actions"],
    )
    _gh_api(
        f"repos/{repo_slug}/actions/permissions/workflow",
        method="PUT",
        payload=bundle["repo_settings"]["workflow"],
    )

    existing = {r["name"]: r["id"] for r in _gh_api(f"repos/{repo_slug}/rulesets")}
    for key in ("main_branch", "release_tags"):
        spec = bundle[key]
        if spec["name"] in existing:
            rs_id = existing[spec["name"]]
            _gh_api(f"repos/{repo_slug}/rulesets/{rs_id}", method="PUT", payload=spec)
        else:
            _gh_api(f"repos/{repo_slug}/rulesets", method="POST", payload=spec)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for --check drift auditing and --apply governance synchronization."""
    parser = argparse.ArgumentParser(description="Sync or audit declarative GitHub governance.")
    parser.add_argument("--repo", default="brandon-fox/alos")
    parser.add_argument("--rulesets-dir", type=Path, default=DEFAULT_RULESETS_DIR)
    parser.add_argument("--apply", action="store_true", help="Apply declarative settings to GitHub")
    parser.add_argument("--force", action="store_true", help="Skip main check-run preflight")
    args = parser.parse_args(argv)

    bundle = load_local_manifests(args.rulesets_dir)
    if args.apply:
        apply_governance(args.repo, bundle, force=args.force)
    live = fetch_live_state(args.repo)
    drift = compute_drift(bundle, live)
    print(json.dumps({"repo": args.repo, "drift_count": len(drift), "findings": drift}, indent=2))
    return 1 if drift else 0


if __name__ == "__main__":
    raise SystemExit(main())
