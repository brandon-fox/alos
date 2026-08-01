#!/usr/bin/env python3
"""
Coverage Gap Analyzer

Analyzes coverage.json, identifies modules in alos/ with <80% coverage,
and generates test stubs for public functions and classes.
"""

import ast
import json
import os
import sys
from pathlib import Path


def extract_public_names(source_code: str) -> tuple[list[str], list[str]]:
    """Extract public function and class names from Python source code."""
    try:
        tree = ast.parse(source_code)
    except Exception as e:
        print(f"Error parsing source: {e}", file=sys.stderr)
        return [], []

    functions = []
    classes = []

    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            functions.append(node.name)
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            classes.append(node.name)

    return functions, classes


def generate_stub_content(module_path: Path, functions: list[str], classes: list[str]) -> str:
    """Generate the content for a test stub file."""
    # Convert path like alos/core/evaluator.py to alos.core.evaluator
    parts = list(module_path.with_suffix("").parts)
    module_import_path = ".".join(parts)

    lines = [
        f'"""Auto-generated test stubs for {module_import_path}.',
        "",
        "These stubs were created by the coverage gap analyzer.",
        "Fill in the test implementations to improve coverage.",
        '"""',
        "import pytest",
        "",
    ]

    names_to_import = functions + classes
    if names_to_import:
        lines.append(f"from {module_import_path} import (")
        for name in names_to_import:
            lines.append(f"    {name},")
        lines.append(")")
        lines.append("")

    for func in functions:
        class_name = "Test" + "".join(word.capitalize() for word in func.split("_"))
        lines.extend(
            [
                "",
                f"class {class_name}:",
                f'    """Tests for {func}."""',
                "",
                f"    def test_{func}_basic(self) -> None:",
                f'        """TODO: Implement test for {func}."""',
                '        pytest.skip("Auto-generated stub \u2014 implement this test")',
                "",
            ]
        )

    for cls in classes:
        class_name = f"Test{cls}"
        lines.extend(
            [
                "",
                f"class {class_name}:",
                f'    """Tests for {cls}."""',
                "",
                f"    def test_{cls.lower()}_basic(self) -> None:",
                f'        """TODO: Implement test for {cls}."""',
                '        pytest.skip("Auto-generated stub \u2014 implement this test")',
                "",
            ]
        )

    return "\n".join(lines)


def _process_coverage_files(
    files_data: dict,
    tests_dir: Path,
) -> list[tuple[str, float, Path]]:
    """Process coverage data and generate test stubs for low-coverage modules."""
    generated_stubs = []

    for file_path_str, file_info in files_data.items():
        if not file_path_str.startswith("alos/") and not file_path_str.startswith(f"alos{os.sep}"):
            continue

        file_path = Path(file_path_str)
        summary = file_info.get("summary", {})
        percent_covered = summary.get("percent_covered", 100.0)

        if percent_covered >= 80.0:
            continue

        try:
            with open(file_path, encoding="utf-8") as f:
                source_code = f.read()
        except Exception as e:
            print(f"Error reading {file_path}: {e}", file=sys.stderr)
            continue

        functions, classes = extract_public_names(source_code)
        if not functions and not classes:
            continue

        module_parts = list(file_path.with_suffix("").parts)
        test_file_name = "test_" + "_".join(module_parts) + ".py"
        test_file_path = tests_dir / test_file_name

        if test_file_path.exists():
            continue

        stub_content = generate_stub_content(file_path, functions, classes)

        try:
            with open(test_file_path, "w", encoding="utf-8") as f:
                f.write(stub_content)
            generated_stubs.append((file_path_str, percent_covered, test_file_path))
        except Exception as e:
            print(f"Error writing to {test_file_path}: {e}", file=sys.stderr)

    return generated_stubs


def main() -> None:
    coverage_file = Path("coverage.json")
    if not coverage_file.exists():
        print(
            f"Error: {coverage_file} not found. Run pytest --cov-report=json:coverage.json first.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        with open(coverage_file, encoding="utf-8") as f:
            cov_data = json.load(f)
    except Exception as e:
        print(f"Error reading {coverage_file}: {e}", file=sys.stderr)
        sys.exit(1)

    files_data = cov_data.get("files", {})
    tests_dir = Path("tests")
    tests_dir.mkdir(exist_ok=True)

    generated_stubs = _process_coverage_files(files_data, tests_dir)

    if generated_stubs:
        print("## Coverage Gap Analyzer Report\n")
        print("| Module | Current Coverage | Test Stub Generated |")
        print("|---|---|---|")
        for orig_file, cov_pct, stub_file in generated_stubs:
            print(f"| `{orig_file}` | {cov_pct:.1f}% | `{stub_file}` |")
        sys.exit(0)
    else:
        print("No gaps found or stubs already exist.")
        sys.exit(1)


if __name__ == "__main__":
    main()
