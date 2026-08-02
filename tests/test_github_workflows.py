"""Meta-test suite for GitHub Actions workflows in ALOS repository.

Validates schema, YAML syntax, required permissions, trigger events,
and required workflow groups.
"""

from pathlib import Path

import pytest
import yaml

WORKFLOWS_DIR = Path(".github/workflows")

REQUIRED_WORKFLOWS = [
    "quality-gate.yml",
    "rust-ci.yml",
    "post-merge-pipeline.yml",
    "security-compliance.yml",
    "release-packaging.yml",
    "speckit-governance.yml",
    "performance-benchmark.yml",
]


@pytest.mark.meta
def test_all_required_workflows_exist() -> None:
    """Verify that all required workflow YAML files exist in .github/workflows/."""
    assert WORKFLOWS_DIR.exists() and WORKFLOWS_DIR.is_dir()
    for wf in REQUIRED_WORKFLOWS:
        wf_path = WORKFLOWS_DIR / wf
        assert wf_path.exists(), f"Workflow file {wf} is missing from .github/workflows/"


@pytest.mark.meta
def test_workflow_yaml_syntax_and_structure() -> None:
    """Verify that all workflow YAML files are valid YAML and contain 'name' and 'jobs'."""
    yaml_files = list(WORKFLOWS_DIR.glob("*.yml")) + list(WORKFLOWS_DIR.glob("*.yaml"))
    assert len(yaml_files) >= len(REQUIRED_WORKFLOWS)

    for wf_path in yaml_files:
        content = wf_path.read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)
        assert isinstance(parsed, dict), f"{wf_path.name} must be a valid YAML object mapping"
        assert "name" in parsed, f"{wf_path.name} is missing 'name' field"
        assert "jobs" in parsed, f"{wf_path.name} is missing 'jobs' field"
        assert isinstance(parsed["jobs"], dict), f"{wf_path.name} 'jobs' must be a dict"
        assert len(parsed["jobs"]) > 0, f"{wf_path.name} has no jobs defined"


@pytest.mark.meta
def test_security_compliance_workflow_jobs() -> None:
    """Verify security-compliance.yml contains expected scanning jobs."""
    wf_path = WORKFLOWS_DIR / "security-compliance.yml"
    assert wf_path.exists(), "security-compliance.yml missing"
    content = wf_path.read_text(encoding="utf-8")
    parsed = yaml.safe_load(content)
    jobs = parsed.get("jobs", {})

    expected_jobs = ["gitleaks-scan", "scorecard-analysis", "codeql-analysis"]
    for job in expected_jobs:
        assert job in jobs, f"Job '{job}' missing from security-compliance.yml"


@pytest.mark.meta
def test_release_packaging_workflow_jobs() -> None:
    """Verify release-packaging.yml contains expected packaging jobs."""
    wf_path = WORKFLOWS_DIR / "release-packaging.yml"
    assert wf_path.exists(), "release-packaging.yml missing"
    content = wf_path.read_text(encoding="utf-8")
    parsed = yaml.safe_load(content)
    jobs = parsed.get("jobs", {})

    expected_jobs = ["build-python-wheel", "build-rust-binary", "docker-build-publish-dryrun"]
    for job in expected_jobs:
        assert job in jobs, f"Job '{job}' missing from release-packaging.yml"


@pytest.mark.meta
def test_speckit_governance_workflow_jobs() -> None:
    """Verify speckit-governance.yml contains expected governance jobs."""
    wf_path = WORKFLOWS_DIR / "speckit-governance.yml"
    assert wf_path.exists(), "speckit-governance.yml missing"
    content = wf_path.read_text(encoding="utf-8")
    parsed = yaml.safe_load(content)
    jobs = parsed.get("jobs", {})

    expected_jobs = ["speckit-matrix-audit", "adr-provenance-check"]
    for job in expected_jobs:
        assert job in jobs, f"Job '{job}' missing from speckit-governance.yml"


@pytest.mark.meta
def test_performance_benchmark_workflow_jobs() -> None:
    """Verify performance-benchmark.yml contains expected benchmark jobs."""
    wf_path = WORKFLOWS_DIR / "performance-benchmark.yml"
    assert wf_path.exists(), "performance-benchmark.yml missing"
    content = wf_path.read_text(encoding="utf-8")
    parsed = yaml.safe_load(content)
    jobs = parsed.get("jobs", {})

    expected_jobs = ["rust-benchmark", "python-microbenchmarks"]
    for job in expected_jobs:
        assert job in jobs, f"Job '{job}' missing from performance-benchmark.yml"


@pytest.mark.meta
def test_quality_gate_enhancements() -> None:
    """Verify quality-gate.yml contains uv-lock-check job."""
    wf_path = WORKFLOWS_DIR / "quality-gate.yml"
    content = wf_path.read_text(encoding="utf-8")
    parsed = yaml.safe_load(content)
    jobs = parsed.get("jobs", {})

    assert "uv-lock-check" in jobs, "uv-lock-check job missing from quality-gate.yml"


@pytest.mark.meta
def test_all_github_actions_use_fixed_hashes() -> None:
    """Verify all GitHub Actions in workflow files use full 40-character commit SHA hashes."""
    import re

    sha_regex = re.compile(r"^[0-9a-fA-F]{40}$")
    uses_regex = re.compile(r"uses:\s*([^\s@]+)@([^\s#]+)")

    unpinned: list[str] = []
    yaml_files = list(WORKFLOWS_DIR.glob("*.yml")) + list(WORKFLOWS_DIR.glob("*.yaml"))

    for wf_path in yaml_files:
        lines = wf_path.read_text(encoding="utf-8").splitlines()
        for idx, line in enumerate(lines, 1):
            match = uses_regex.search(line)
            if match:
                action, ref = match.group(1), match.group(2)
                # Ignore local action references starting with ./
                if action.startswith("./"):
                    continue
                if not sha_regex.match(ref):
                    unpinned.append(f"{wf_path.name}:{idx} -> {action}@{ref}")

    assert not unpinned, (
        f"Found {len(unpinned)} unpinned GitHub Actions (must use 40-char commit SHA):\n"
        + "\n".join(unpinned)
    )
