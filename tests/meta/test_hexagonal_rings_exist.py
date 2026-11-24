"""Meta-tests verifying the four Hexagonal Architecture ring packages exist.

Spec: specs/036-hexagonal-twelve-factor-refactor/spec.md (FR-3610)
ADRs: docs/adr/0024 (Hexagonal Ports and Adapters Architecture)
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

HEXAGONAL_RINGS: tuple[tuple[str, str], ...] = (
    ("domain", "Ring 1"),
    ("application", "Ring 2"),
    ("adapters", "Ring 3"),
    ("config", "Ring 4"),
)


@pytest.mark.meta
@pytest.mark.parametrize(("ring_name", "ring_marker"), HEXAGONAL_RINGS)
def test_hexagonal_ring_package_exists_with_docstring(ring_name: str, ring_marker: str) -> None:
    """Verify each Hexagonal ring package exists, imports cleanly, and documents its ring."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    init_file = repo_root / "alos" / ring_name / "__init__.py"
    assert init_file.is_file(), f"Missing Hexagonal ring package initializer: {init_file}"

    module = importlib.import_module(f"alos.{ring_name}")
    assert module.__doc__ is not None and ring_marker in module.__doc__, (
        f"alos.{ring_name}.__doc__ must document '{ring_marker}'"
    )
    assert isinstance(module.__all__, list)
