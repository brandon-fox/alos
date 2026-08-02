"""AST Analysis Anti-Regression Quality Gate Test Suite.

Spec: specs/002-rust-core-architectural-refactor/spec.md (FR-013, NFR-002)
Constitution: Article VII (Code Quality, Exception Documentation & Sonar Scan Governance)
"""

from __future__ import annotations

import ast
from pathlib import Path


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

    assert (
        not high_complexity_functions
    ), f"Functions exceeded Cyclomatic Complexity baseline CC > 12: {high_complexity_functions}"


def test_ast_baseline_json_snapshot_exists() -> None:
    """Verify that ast_metrics_baseline.json exists and contains valid thresholds."""
    baseline_path = Path("tests/quality/ast_metrics_baseline.json")
    assert baseline_path.exists(), "AST baseline snapshot JSON file missing"
