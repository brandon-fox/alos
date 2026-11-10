"""Pytest configuration and BDD lifecycle fixtures for ALOS test suite."""

from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def bdd_context() -> dict[str, Any]:
    """Shared state dictionary passed across Given, When, and Then step definitions."""
    return {}


@pytest.fixture
def tmp_vault(tmp_path: Path) -> Path:
    """Fixture providing a initialized temporary Obsidian vault directory structure."""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)

    profile_file = vault_dir / "USER_PROFILE.md"
    profile_file.write_text(
        "---\ntags: [profile, executive]\ntype: user_profile\n---\n"
        "User: Alex\nTimezone: America/New_York\n",
        encoding="utf-8",
    )

    preferences_file = vault_dir / "PREFERENCES.md"
    preferences_file.write_text(
        "---\ntags: [preferences]\ntype: rules\n---\n"
        "Rules:\n- No meetings scheduled after 5:00 PM\n",
        encoding="utf-8",
    )

    ledger_file = vault_dir / "CORRECTION_LEDGER.md"
    ledger_file.write_text(
        "---\ntags: [ledger, corrections]\ntype: history\n---\n"
        "History:\n- Never book flights without checking Delta options first\n",
        encoding="utf-8",
    )

    return vault_dir


def pytest_bdd_before_scenario(request: Any, feature: Any, scenario: Any) -> None:
    """Lifecycle hook executed before every BDD scenario starts."""
    pass


def pytest_bdd_after_scenario(request: Any, feature: Any, scenario: Any) -> None:
    """Lifecycle hook executed after every BDD scenario completes."""
    pass
