"""Global Pytest configuration, BDD fixtures, worker isolation, OS markers, and Hypothesis profiles.

Spec: specs/035-parallel-testing-and-qa-matrix/spec.md (FR-001, FR-002, FR-009, FR-011)
"""

from __future__ import annotations

import os
import random
import sys
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, Phase, Verbosity, settings

from alos.logs.telemetry import global_tracer

settings.register_profile(
    "fast",
    max_examples=25,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    phases=[Phase.explicit, Phase.reuse, Phase.generate, Phase.shrink],
)
settings.register_profile(
    "deep",
    max_examples=150,
    deadline=None,
    derandomize=False,
    verbosity=Verbosity.normal,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "fast"))


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register deterministic seed replay and live-requirement CLI options."""
    parser.addoption(
        "--seed",
        action="store",
        default=None,
        type=int,
        help="Deterministic PRNG seed for test reproducibility.",
    )
    parser.addoption(
        "--require-live",
        action="store_true",
        default=False,
        help="Fail instead of skipping @live / @docker tests when hardware is unavailable.",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Apply OS-specific skip markers and serialize Docker-exclusive tests under xdist."""
    is_win = sys.platform == "win32"
    is_linux = sys.platform.startswith("linux")

    for item in items:
        if "windows_only" in item.keywords and not is_win:
            item.add_marker(pytest.mark.skip(reason="Requires Windows host"))
        if "linux_only" in item.keywords and not is_linux:
            item.add_marker(pytest.mark.skip(reason="Requires Linux host"))
        if "docker" in item.keywords or "live" in item.keywords:
            item.add_marker(pytest.mark.xdist_group(name="hardware_exclusive"))


@pytest.fixture
def bdd_context() -> dict[str, Any]:
    """Shared state dictionary passed across Given, When, and Then step definitions."""
    return {}


@pytest.fixture
def tmp_vault(tmp_path: Path) -> Path:
    """Fixture providing an initialized temporary Obsidian vault directory structure."""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)

    (vault_dir / "USER_PROFILE.md").write_text(
        "---\ntags: [profile, executive]\ntype: user_profile\n---\n"
        "User: Alex\nTimezone: America/New_York\n",
        encoding="utf-8",
    )
    (vault_dir / "PREFERENCES.md").write_text(
        "---\ntags: [preferences]\ntype: rules\n---\n"
        "Rules:\n- No meetings scheduled after 5:00 PM\n",
        encoding="utf-8",
    )
    (vault_dir / "CORRECTION_LEDGER.md").write_text(
        "---\ntags: [ledger, corrections]\ntype: history\n---\n"
        "History:\n- Never book flights without checking Delta options first\n",
        encoding="utf-8",
    )
    return vault_dir


def pytest_bdd_before_scenario(request: Any, feature: Any, scenario: Any) -> None:
    """Lifecycle hook executed before every BDD scenario starts."""


def pytest_bdd_after_scenario(request: Any, feature: Any, scenario: Any) -> None:
    """Lifecycle hook executed after every BDD scenario completes."""


@pytest.fixture(autouse=True)
def _isolate_alos_test_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> Generator[None, None, None]:
    """Guarantee every parallel worker/test uses isolated ALOS_HOME, logs, env, and tracer."""
    seed = request.config.getoption("--seed")
    if seed is not None:
        random.seed(int(seed))

    isolated_home = tmp_path / "_alos_isolated_home"
    logs_dir = isolated_home / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("ALOS_HOME", str(isolated_home))
    monkeypatch.setenv("ALOS_AUDIT_LOG_PATH", str(logs_dir / "system_audit.jsonl"))
    monkeypatch.setenv("ALOS_DECISION_LOG_PATH", str(logs_dir / "decision_log.jsonl"))
    monkeypatch.setenv("ALOS_WORKFLOWS_DIR", str(isolated_home / "workflows"))
    monkeypatch.delenv("ALOS_QUEUE_DB_URL", raising=False)
    monkeypatch.delenv("ALOS_MOCK_SENSOR_JSON", raising=False)
    monkeypatch.delenv("ALOS_SWARM_MODE", raising=False)

    global_tracer.clear()
    yield
    global_tracer.clear()
