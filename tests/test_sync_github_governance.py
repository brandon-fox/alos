"""Unit tests for declarative GitHub governance sync, drift detection, and sentinel."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_gov_module() -> Any:
    script = REPO_ROOT / "scripts" / "sync_github_governance.py"
    assert script.is_file(), "scripts/sync_github_governance.py missing"
    spec = importlib.util.spec_from_file_location("sync_github_governance", script)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_declarative_ruleset_manifests_exist_and_enforce_enterprise_controls() -> None:
    """Spec 038 FR-010: Repo settings, main branch, and v* release tag manifests must exist."""
    mod = _load_gov_module()
    bundle = mod.load_local_manifests(REPO_ROOT / ".github" / "rulesets")

    assert bundle["repo_settings"]["repo"]["squash_merge_commit_title"] == "PR_TITLE"
    assert bundle["repo_settings"]["repo"]["allow_rebase_merge"] is False
    assert bundle["repo_settings"]["actions"]["sha_pinning_required"] is True

    main_rules = {r["type"]: r for r in bundle["main_branch"]["rules"]}
    expected_types = {
        "deletion",
        "non_fast_forward",
        "required_linear_history",
        "required_signatures",
    }
    assert expected_types <= set(main_rules)
    assert main_rules["pull_request"]["parameters"]["required_review_thread_resolution"] is True
    assert main_rules["code_coverage"]["parameters"]["minimum_coverage"] == 90
    checks = [
        c["context"]
        for c in main_rules["required_status_checks"]["parameters"]["required_status_checks"]
    ]
    assert "ci-merge-gate" in checks

    tag_rules = {r["type"] for r in bundle["release_tags"]["rules"]}
    assert {"deletion", "non_fast_forward", "update"} <= tag_rules
    assert "refs/tags/v*" in bundle["release_tags"]["conditions"]["ref_name"]["include"]


def test_drift_detection_flags_drifted_settings_and_multi_collaborator_sentinel() -> None:
    """Spec 038 FR-010: Detect drifted ruleset fields and alert when >1 collaborator exists."""
    mod = _load_gov_module()
    bundle = mod.load_local_manifests(REPO_ROOT / ".github" / "rulesets")

    clean_live = {
        "repo": dict(bundle["repo_settings"]["repo"]),
        "actions": dict(bundle["repo_settings"]["actions"]),
        "workflow": dict(bundle["repo_settings"]["workflow"]),
        "rulesets": {
            "main": dict(bundle["main_branch"], id=20200177),
            "release-tags": dict(bundle["release_tags"], id=20200999),
        },
        "collaborators": [{"login": "brandon-fox", "type": "User"}],
    }
    assert mod.compute_drift(bundle, clean_live) == []

    drifted_live = {
        **clean_live,
        "actions": {"enabled": True, "allowed_actions": "all", "sha_pinning_required": False},
        "rulesets": {"main": dict(bundle["main_branch"], id=20200177)},
        "collaborators": [
            {"login": "brandon-fox", "type": "User"},
            {"login": "second-maintainer", "type": "User"},
        ],
    }
    findings = mod.compute_drift(bundle, drifted_live)
    codes = {f["category"] for f in findings}
    assert "actions_permissions" in codes
    assert "missing_ruleset:release-tags" in codes
    assert "collaborator_review_escalation_needed" in codes


def test_preflight_blocks_apply_when_required_check_has_never_run_on_main() -> None:
    """Spec 038 Edge Case: Prevent self-deadlock if ci-merge-gate has not reported on main."""
    mod = _load_gov_module()
    bundle = mod.load_local_manifests(REPO_ROOT / ".github" / "rulesets")
    with pytest.raises(RuntimeError, match="ci-merge-gate"):
        mod.verify_main_checks_exist(bundle["main_branch"], observed_check_names={"ruff-lint"})
    mod.verify_main_checks_exist(
        bundle["main_branch"], observed_check_names={"ci-merge-gate", "ruff-lint"}
    )


def test_oss_templates_and_security_policy_exist() -> None:
    """Spec 038 FR-005: Verify PR/Issue templates, CONTRIBUTING.md, and SECURITY.md."""
    assert (REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md").is_file()
    assert (REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml").is_file()
    assert (REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "feature_request.yml").is_file()
    assert (REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "config.yml").is_file()
    assert (REPO_ROOT / "CONTRIBUTING.md").is_file()
    sec = (REPO_ROOT / "SECURITY.md").read_text(encoding="utf-8")
    assert "0.1.x" in sec
