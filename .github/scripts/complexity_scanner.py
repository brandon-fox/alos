#!/usr/bin/env python3
"""
Complexity Scanner

Uses radon to compute cyclomatic complexity and maintainability index
for Python files in the alos/ directory.
Flags complex functions and low-maintainability modules.
"""

import sys
from pathlib import Path

try:
    from radon.complexity import cc_visit
    from radon.metrics import mi_visit
except ImportError:
    print("Error: radon is not installed. Please run 'pip install radon'.", file=sys.stderr)
    sys.exit(1)


def grade_cc(cc: int) -> str:
    """Return cyclomatic complexity grade."""
    if cc <= 5:
        return "A"
    elif cc <= 10:
        return "B"
    elif cc <= 20:
        return "C"
    elif cc <= 30:
        return "D"
    elif cc <= 40:
        return "E"
    else:
        return "F"


def _scan_complexity(alos_dir: Path) -> tuple[list[dict], list[dict]]:
    """Scan all Python files for complexity hotspots."""
    hotspots_cc: list[dict] = []
    hotspots_mi: list[dict] = []

    for file_path in alos_dir.rglob("*.py"):
        try:
            with open(file_path, encoding="utf-8") as f:
                source = f.read()
        except Exception as e:
            print(f"Error reading {file_path}: {e}", file=sys.stderr)
            continue

        _analyze_cc(source, file_path, hotspots_cc)
        _analyze_mi(source, file_path, hotspots_mi)

    return hotspots_cc, hotspots_mi


def _analyze_cc(source: str, file_path: Path, hotspots: list[dict]) -> None:
    """Analyze cyclomatic complexity for a single file."""
    try:
        blocks = cc_visit(source)
        for block in blocks:
            if hasattr(block, "is_method") or type(block).__name__ == "Function":
                cc = block.complexity
                lines = block.endline - block.lineno + 1
                grade = grade_cc(cc)
                if cc > 10 or lines > 50:
                    hotspots.append(
                        {
                            "file": str(file_path),
                            "function": block.name,
                            "complexity": cc,
                            "grade": grade,
                            "lines": lines,
                        }
                    )
    except Exception as e:
        print(f"Error computing CC for {file_path}: {e}", file=sys.stderr)


def _analyze_mi(source: str, file_path: Path, hotspots: list[dict]) -> None:
    """Analyze maintainability index for a single file."""
    try:
        mi = mi_visit(source, multi=True)
        if mi < 20:
            hotspots.append({"file": str(file_path), "mi": mi})
    except Exception as e:
        print(f"Error computing MI for {file_path}: {e}", file=sys.stderr)


def _print_report(hotspots_cc: list[dict], hotspots_mi: list[dict]) -> None:
    """Print the complexity report in markdown format."""
    print("# Code Complexity Report\n")

    if hotspots_cc:
        print("## Complex Functions (CC > 10 or Lines > 50)\n")
        print("| File | Function | CC Score | Grade | Lines |")
        print("|---|---|---|---|---|")
        for h in hotspots_cc:
            file_col = f"`{h['file']}`"
            func_col = f"`{h['function']}`"
            print(f"| {file_col} | {func_col} | {h['complexity']} | {h['grade']} | {h['lines']} |")
        print("\n")

    if hotspots_mi:
        print("## Low Maintainability Modules (MI < 20)\n")
        print("| File | Maintainability Index |")
        print("|---|---|")
        for h in hotspots_mi:
            print(f"| `{h['file']}` | {h['mi']:.2f} |")
        print("\n")


def main() -> None:
    alos_dir = Path("alos")
    if not alos_dir.exists():
        print(f"Error: {alos_dir} directory not found.", file=sys.stderr)
        sys.exit(1)

    hotspots_cc, hotspots_mi = _scan_complexity(alos_dir)
    has_findings = bool(hotspots_cc or hotspots_mi)

    if has_findings:
        hotspots_cc.sort(key=lambda x: x["complexity"], reverse=True)
        hotspots_mi.sort(key=lambda x: x["mi"])
        _print_report(hotspots_cc, hotspots_mi)
        sys.exit(0)
    else:
        print("No complexity hotspots found. All code is clean!")
        sys.exit(1)


if __name__ == "__main__":
    main()
