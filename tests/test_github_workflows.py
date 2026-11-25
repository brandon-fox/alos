"""Meta-test suite for consolidated GitHub Actions workflows in ALOS repository.

Validates schema, YAML syntax, SHA pinning, job timeouts, fork-PR guards,
template-injection elimination, and consolidated Spec 038 / Spec 033 invariants.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

WORKFLOWS_DIR = Path(".github/workflows")

REQUIRED_WORKFLOWS = [
    "quality-gate.yml",
    "auto-merge.yml",
    "post-merge-pipeline.yml",
    "security-compliance.yml",
    "release-packaging.yml",
]

RETIRED_PR_SPRAWL_WORKFLOWS = [
    "ade-axioms.yml",
    "autofix.yml",
    "pr-title-lint.yml",
    "rust-ci.yml",
    "sandbox-ci.yml",
]


@pytest.mark.meta
def test_required_workflows_exist_and_sprawl_workflows_are_retired() -> None:
    """Spec 038 FR-001: Required workflow groups exist and superseded PR sprawl files are gone."""
    assert WORKFLOWS_DIR.exists() and WORKFLOWS_DIR.is_dir()
    for wf in REQUIRED_WORKFLOWS:
        assert (WORKFLOWS_DIR / wf).exists(), f"Workflow {wf} missing from .github/workflows/"
    for retired in RETIRED_PR_SPRAWL_WORKFLOWS:
        assert not (WORKFLOWS_DIR / retired).exists(), f"Superseded workflow {retired} still exists"


@pytest.mark.meta
def test_workflow_yaml_syntax_and_structure() -> None:
    """Verify that all workflow YAML files are valid YAML and contain 'name' and 'jobs'."""
    yaml_files = sorted(WORKFLOWS_DIR.glob("*.yml")) + sorted(WORKFLOWS_DIR.glob("*.yaml"))
    assert len(yaml_files) >= len(REQUIRED_WORKFLOWS)

    for wf_path in yaml_files:
        parsed = yaml.safe_load(wf_path.read_text(encoding="utf-8"))
        assert isinstance(parsed, dict), f"{wf_path.name} must be a valid YAML object mapping"
        assert "name" in parsed, f"{wf_path.name} is missing 'name' field"
        assert "jobs" in parsed and isinstance(parsed["jobs"], dict) and parsed["jobs"]


@pytest.mark.meta
def test_consolidated_quality_gate_lanes_and_merge_gate() -> None:
    """Spec 038 FR-001..FR-006: Verify consolidated cached lanes and terminal ci-merge-gate."""
    content = (WORKFLOWS_DIR / "quality-gate.yml").read_text(encoding="utf-8")
    parsed = yaml.safe_load(content)
    triggers = parsed.get("on", parsed.get(True, {}))
    assert {"pull_request", "merge_group", "push", "workflow_dispatch"} <= set(triggers)

    jobs = parsed["jobs"]
    expected_jobs = {
        "pr-size",
        "pr-governance",
        "changes",
        "python-static",
        "pytest-suite",
        "pytest-windows",
        "combined-coverage",
        "qa-deep-fanout",
        "rust-checks",
        "rust-windows",
        "rust-native-parity-and-mutants",
        "dependency-review",
        "docker-validate",
        "ci-merge-gate",
    }
    assert expected_jobs <= set(jobs)
    for collapsed in (
        "uv-lock-check",
        "ruff-lint",
        "mypy-types",
        "bandit-security",
        "adr-governance",
    ):
        assert collapsed not in jobs, f"{collapsed} must be folded into 1-VM python-static"

    assert jobs["ci-merge-gate"].get("if") == "always()"
    assert set(jobs["ci-merge-gate"]["needs"]) == expected_jobs - {"ci-merge-gate"}
    assert "continue-on-error" not in content
    assert "${{" not in "\n".join(
        step.get("run", "")
        for job in jobs.values()
        if isinstance(job, dict)
        for step in job.get("steps", [])
    )
    assert "First-ADE/.github/.github/actions/ade-axioms@" in content and "gpgsig" in content
    assert "EmbarkStudios/cargo-deny-action@" in content
    assert "mkdocs build --strict" in content
    assert "pyadr check-adr-repo" in content
    assert "scope=alos-sandbox-base" in content and "scope=alos-sandbox-full" in content


@pytest.mark.meta
def test_security_compliance_and_release_packaging_jobs() -> None:
    """Verify security-compliance.yml and release-packaging.yml retain required jobs."""
    sec_jobs = yaml.safe_load((WORKFLOWS_DIR / "security-compliance.yml").read_text("utf-8"))[
        "jobs"
    ]
    assert {"gitleaks-scan", "scorecard-analysis", "codeql-analysis"} <= set(sec_jobs)

    rel_jobs = yaml.safe_load((WORKFLOWS_DIR / "release-packaging.yml").read_text("utf-8"))["jobs"]
    assert rel_jobs, "release-packaging.yml must define packaging jobs"


@pytest.mark.meta
def test_all_github_actions_use_fixed_hashes() -> None:
    """Verify all GitHub Actions in workflow and local composite action files use 40-char SHAs."""
    sha_regex = re.compile(r"^[0-9a-fA-F]{40}$")
    uses_regex = re.compile(r"uses:\s*([^\s@]+)@([^\s#]+)")

    unpinned: list[str] = []
    targets = sorted(WORKFLOWS_DIR.glob("*.yml")) + sorted(Path(".github/actions").glob("*/*.yml"))

    for wf_path in targets:
        for idx, line in enumerate(wf_path.read_text(encoding="utf-8").splitlines(), 1):
            match = uses_regex.search(line)
            if not match or match.group(1).startswith("./"):
                continue
            if not sha_regex.match(match.group(2)):
                unpinned.append(f"{wf_path}:{idx} -> {match.group(1)}@{match.group(2)}")

    assert not unpinned, "Unpinned GitHub Actions:\n" + "\n".join(unpinned)


@pytest.mark.meta
def test_pinned_actions_carry_a_version_comment() -> None:
    """Spec 028 FR-002: Every SHA-pinned action carries a trailing release/branch comment."""
    uses_regex = re.compile(r"uses:\s*([^\s@]+)@([^\s#]+)\s*(#\s*(\S.*))?$")
    uncommented: list[str] = []
    targets = sorted(WORKFLOWS_DIR.glob("*.yml")) + sorted(Path(".github/actions").glob("*/*.yml"))

    for wf_path in targets:
        for idx, line in enumerate(wf_path.read_text(encoding="utf-8").splitlines(), 1):
            match = uses_regex.search(line)
            if match and not match.group(1).startswith("./") and not match.group(4):
                uncommented.append(f"{wf_path}:{idx} -> {match.group(1)}@{match.group(2)}")

    assert not uncommented, "Pinned actions missing version comment:\n" + "\n".join(uncommented)


@pytest.mark.meta
def test_every_job_has_a_timeout() -> None:
    """Every non-reusable job sets timeout-minutes between 1 and 60."""
    missing: list[str] = []
    for wf_path in sorted(WORKFLOWS_DIR.glob("*.yml")):
        jobs = yaml.safe_load(wf_path.read_text(encoding="utf-8")).get("jobs", {})
        for name, job in jobs.items():
            if "uses" in job:
                continue
            minutes = job.get("timeout-minutes")
            if not isinstance(minutes, int) or not 1 <= minutes <= 60:
                missing.append(f"{wf_path.name}:{name}")
    assert not missing, f"Jobs without a timeout-minutes between 1 and 60: {missing}"


@pytest.mark.meta
def test_coverage_floor_is_enforced() -> None:
    """The test job must fail when coverage drops below the 90% floor."""
    content = (WORKFLOWS_DIR / "quality-gate.yml").read_text(encoding="utf-8")
    assert "--cov-fail-under=90" in content
    assert "--fail-under=90" in content


@pytest.mark.meta
def test_vetted_automerge_signed_rebase_and_autofix_consolidation() -> None:
    """Spec 033 & Spec 038 FR-005: Vetted draft promotion, non-owner review gate, and rebase."""
    auto_merge = (WORKFLOWS_DIR / "auto-merge.yml").read_text(encoding="utf-8")
    parsed = yaml.safe_load(auto_merge)
    triggers = parsed.get("on", parsed.get(True, {}))
    assert {"push", "pull_request", "workflow_run", "schedule"} <= set(triggers)
    assert "check_run" not in triggers, "check_run cascade storm must remain retired"
    assert "signed_pr_rebase.py" in auto_merge
    assert "./.github/actions/setup-git-signing" in auto_merge
    assert "PR_QUEUE_TOKEN" in auto_merge and "'ready'" in auto_merge and "pr.draft" in auto_merge
    assert "ci-merge-gate" in auto_merge and "gatePassed" in auto_merge
    assert "APPROVED" in auto_merge and "brandon-fox" in auto_merge
    assert "autofix" in parsed["jobs"]
    assert "github.actor != 'dependabot[bot]'" not in auto_merge
    assert "github.actor != 'github-actions[bot]'" not in auto_merge
    assert "${{" not in "\n".join(
        step.get("run", "")
        for job in parsed["jobs"].values()
        if isinstance(job, dict)
        for step in job.get("steps", [])
    )

    signing_action = Path(".github/actions/setup-git-signing/action.yml").read_text("utf-8")
    assert "gpg.format" in signing_action and "commit.gpgsign" in signing_action
