"""AST Analysis Anti-Regression Quality Gate Meta Test Suite.

Spec: specs/003-rust-core-architectural-refactor/spec.md (FR-013, NFR-002)
Constitution: Article VII (Code Quality, Exception Documentation & Sonar Scan Governance)
"""

from __future__ import annotations

import ast
from functools import lru_cache
from pathlib import Path

import pytest


class CyclomaticComplexityVisitor(ast.NodeVisitor):
    """AST Node Visitor computing Cyclomatic Complexity (CC) per function."""

    def __init__(self) -> None:
        self.complexity: int = 1

    def visit_If(self, node: ast.If) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        self.complexity += len(node.values) - 1
        self.generic_visit(node)


def compute_function_complexity(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Compute Cyclomatic Complexity for a single AST function node."""
    visitor = CyclomaticComplexityVisitor()
    visitor.visit(node)
    return visitor.complexity


@lru_cache(maxsize=256)
def analyze_file_ast(file_path: Path) -> list[tuple[str, int]]:
    """Parse Python source file into AST and analyze function complexity."""
    content = file_path.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(file_path))
    results: list[tuple[str, int]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            cc = compute_function_complexity(node)
            func_name = f"{file_path.name}:{node.name}"
            results.append((func_name, cc))

    return results


@pytest.mark.meta
def test_ast_cyclomatic_complexity_cap() -> None:
    """Verify all functions across alos/ satisfy Cyclomatic Complexity CC <= 12
    (pre-refactor baseline max 11 in vector_store.py).
    """
    alos_dir = Path("alos")
    high_complexity_functions: list[tuple[str, int]] = []

    for py_file in alos_dir.glob("**/*.py"):
        if py_file.name == "__init__.py":
            continue
        file_results = analyze_file_ast(py_file)
        for func_name, cc in file_results:
            if cc > 12:
                high_complexity_functions.append((func_name, cc))

    assert not high_complexity_functions, (
        f"Functions exceeded Cyclomatic Complexity baseline CC > 12: {high_complexity_functions}"
    )


@pytest.mark.meta
def test_ast_baseline_json_snapshot_exists() -> None:
    """Verify that ast_metrics_baseline.json exists and contains valid thresholds."""
    baseline_path = Path("tests/meta/ast_metrics_baseline.json")
    assert baseline_path.exists(), "AST baseline snapshot JSON file missing"


@pytest.mark.meta
def test_inline_suppressions_are_specific_and_justified() -> None:
    """Constitution VII / Spec 038 FR-008: Disallow bare suppressions and ratchet unjustified."""
    import io
    import json
    import re
    import tokenize

    bare_re = re.compile(r"#\s*(?:noqa(?!\s*:)|type:\s*ignore(?!\s*\[))")
    supp_re = re.compile(
        r"#\s*(?:noqa:\s*[A-Z0-9,\s]+|type:\s*ignore\[[^\]]+\]|pragma:\s*no\s*cover|NOSONAR)"
    )
    directive_only_re = re.compile(
        r"^(?:#\s*(?:noqa:\s*[A-Z0-9,\s]+|type:\s*ignore\[[^\]]+\]|nosec[^#]*|pragma:\s*no\s*cover|NOSONAR)\s*)+$"
    )

    bare_hits: list[str] = []
    unjustified: list[str] = []
    for folder in ("alos", "tests"):
        for py_file in sorted(Path(folder).rglob("*.py")):
            source = py_file.read_text(encoding="utf-8")
            lines = source.splitlines()
            comments_by_line: dict[int, str] = {}
            for tok in tokenize.generate_tokens(io.StringIO(source).readline):
                if tok.type == tokenize.COMMENT:
                    comments_by_line[tok.start[0]] = tok.string

            for lineno, comment_part in sorted(comments_by_line.items()):
                if bare_re.search(comment_part):
                    bare_hits.append(f"{py_file}:{lineno}: {lines[lineno - 1].strip()}")
                if not supp_re.search(comment_part):
                    continue
                inline_has_prose = not directive_only_re.match(comment_part.strip())
                prev_has_prose = any(
                    ln in comments_by_line
                    and not directive_only_re.match(comments_by_line[ln].strip())
                    for ln in range(max(1, lineno - 3), lineno)
                )
                if not (inline_has_prose or prev_has_prose):
                    unjustified.append(f"{py_file}:{lineno}: {lines[lineno - 1].strip()}")

    assert not bare_hits, "Bare # noqa or # type: ignore forbidden:\n" + "\n".join(bare_hits)
    cap = json.loads(Path("tests/meta/ast_metrics_baseline.json").read_text(encoding="utf-8"))[
        "thresholds"
    ]["max_legacy_unjustified_suppressions"]
    assert len(unjustified) <= cap, (
        f"Unjustified inline suppressions ({len(unjustified)} > {cap}); add a technical "
        f"justification comment:\n" + "\n".join(unjustified)
    )
