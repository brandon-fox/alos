"""AST import-boundary meta-tests enforcing Hexagonal inward-only dependencies.

Spec: specs/036-hexagonal-twelve-factor-refactor/spec.md (FR-3610, SC-001)
ADRs: docs/adr/0024 (Hexagonal Ports and Adapters Architecture)
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ALLOWED_STDLIB = sys.stdlib_module_names | frozenset({"__future__"})
ALLOWED_THIRD_PARTY = frozenset({"pydantic"})
RING_ALLOWED_ALOS: dict[str, tuple[str, ...]] = {
    "domain": ("alos.domain",),
    "application": ("alos.domain", "alos.application"),
}


def _resolve_import_from(py_file: Path, node: ast.ImportFrom) -> str:
    """Resolve an ast.ImportFrom node (absolute or relative) to a dotted module path."""
    if node.level == 0:
        return node.module or ""
    pkg_parts = py_file.relative_to(REPO_ROOT).with_suffix("").parts[:-1]
    keep = len(pkg_parts) - (node.level - 1)
    if keep <= 0:
        return "<escaped-root>"
    base = ".".join(pkg_parts[:keep])
    return f"{base}.{node.module}" if node.module else base


def _check_target(target: str, ring: str) -> str | None:
    """Return an error description if target violates ring boundaries, else None."""
    top = target.split(".", maxsplit=1)[0]
    if top == "alos":
        allowed = RING_ALLOWED_ALOS[ring]
        if any(target == prefix or target.startswith(f"{prefix}.") for prefix in allowed):
            return None
        return f"forbidden internal import '{target}'"
    if top in ALLOWED_STDLIB or top in ALLOWED_THIRD_PARTY:
        return None
    return f"forbidden external import '{target}'"


def _collect_ring_violations(ring: str) -> list[str]:
    """Scan all Python modules inside alos/<ring> for outward AST imports."""
    violations: list[str] = []
    for py_file in sorted((REPO_ROOT / "alos" / ring).rglob("*.py")):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        rel = py_file.relative_to(REPO_ROOT)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                targets = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                targets = [_resolve_import_from(py_file, node)]
            else:
                continue
            for target in targets:
                err = _check_target(target, ring)
                if err is not None:
                    violations.append(f"{rel}:{node.lineno}: {err}")
    return violations


@pytest.mark.meta
@pytest.mark.parametrize("ring", ("domain", "application"))
def test_hexagonal_ring_inward_imports_only(ring: str) -> None:
    """Verify alos.domain and alos.application only import inward/allowed dependencies."""
    violations = _collect_ring_violations(ring)
    assert not violations, f"Hexagonal boundary violations in alos.{ring}:\n" + "\n".join(
        violations
    )
