"""Meta-tests enforcing Spec 038 PR-02 hooks, MkDocs, Rust Cargo.lock/deny, and Docker."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.meta
def test_precommit_has_no_sham_hooks_and_enforces_coverage_floor() -> None:
    """Spec 038 FR-008: Remove sham print() hooks and enforce >=90% cov on pre-push."""
    raw = (REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    assert "print('Sonar" not in raw, "Sham print('Sonar...') hooks must be removed"
    assert "--cov-fail-under=90" in raw, "pre-push pytest gate must enforce --cov-fail-under=90"
    assert "mkdocs build --strict" in raw, "pre-push must validate mkdocs build --strict"


@pytest.mark.meta
def test_mkdocs_strict_build_passes(tmp_path: Path) -> None:
    """Spec 038 FR-005: mkdocs.yml must set strict: true and build cleanly."""
    mkdocs_yml = REPO_ROOT / "mkdocs.yml"
    assert mkdocs_yml.is_file(), "mkdocs.yml missing from repository root"
    cfg = yaml.safe_load(mkdocs_yml.read_text(encoding="utf-8"))
    assert cfg.get("strict") is True, "mkdocs.yml must set strict: true"
    proc = subprocess.run(  # noqa: S603 - fixed sys.executable mkdocs invocation in tmp_path
        [sys.executable, "-m", "mkdocs", "build", "--strict", "-d", str(tmp_path / "site")],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"mkdocs build --strict failed:\n{proc.stdout}\n{proc.stderr}"


@pytest.mark.meta
def test_rust_cargo_lock_and_cargo_deny_exist() -> None:
    """Spec 038 FR-007: Cargo.lock and deny.toml must exist for reproducible Rust builds."""
    cargo_lock = REPO_ROOT / "crates" / "alos_native" / "Cargo.lock"
    assert cargo_lock.is_file(), "crates/alos_native/Cargo.lock must be committed"
    lock_text = cargo_lock.read_text(encoding="utf-8")
    assert 'name = "alos_native"' in lock_text and 'name = "pyo3"' in lock_text

    deny_toml = REPO_ROOT / "deny.toml"
    assert deny_toml.is_file(), "deny.toml must exist at repository root"
    deny_text = deny_toml.read_text(encoding="utf-8")
    for section in ("[advisories]", "[licenses]", "[bans]", "[sources]"):
        assert section in deny_text, f"Missing {section} in deny.toml"


@pytest.mark.meta
def test_dependabot_covers_all_four_ecosystems_with_groups() -> None:
    """Spec 038 FR-007: dependabot.yml must cover uv, cargo, github-actions, and docker."""
    dep_cfg = yaml.safe_load((REPO_ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8"))
    updates = {u["package-ecosystem"]: u for u in dep_cfg.get("updates", [])}
    assert {"uv", "cargo", "github-actions", "docker"} <= set(updates), (
        f"Missing ecosystems in dependabot.yml: {set(updates)}"
    )
    assert updates["cargo"]["directory"] == "/crates/alos_native"
    assert "groups" in updates["github-actions"], "github-actions updates must be grouped"
    assert "groups" in updates["uv"], "uv updates must be grouped"


@pytest.mark.meta
def test_dockerignore_and_hardened_non_root_dockerfile() -> None:
    """Spec 038 FR-009: .dockerignore and non-root locked Dockerfile must exist."""
    dockerignore = REPO_ROOT / ".dockerignore"
    assert dockerignore.is_file(), ".dockerignore missing"
    ignore_text = dockerignore.read_text(encoding="utf-8")
    for entry in (".git", ".venv", "__pycache__", "tests"):
        assert entry in ignore_text, f".dockerignore must exclude {entry}"

    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "uv.lock" in dockerfile and "--frozen" in dockerfile, (
        "Dockerfile must install from uv.lock --frozen"
    )
    assert "\nUSER " in dockerfile and "USER root" not in dockerfile.splitlines()[-3:], (
        "Dockerfile runtime stage must drop privileges to non-root USER"
    )
    assert "HEALTHCHECK " in dockerfile, "Dockerfile must declare HEALTHCHECK"
    assert "org.opencontainers.image.source" in dockerfile, (
        "Dockerfile must include OCI source label"
    )
