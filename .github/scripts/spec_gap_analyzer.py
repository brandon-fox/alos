#!/usr/bin/env python3
"""
Spec Gap Analyzer

Compares alos/ subpackages against specs/ and tests/features/.
Identifies missing specs, orphaned specs, and missing features.
Outputs a Markdown report to stdout.
"""

import re
import sys
from pathlib import Path


def get_alos_subpackages(alos_dir: Path) -> set[str]:
    """Return a set of subpackage names in alos/."""
    subpackages = set()
    if not alos_dir.exists():
        return subpackages

    for p in alos_dir.iterdir():
        if p.is_dir() and (p / "__init__.py").exists():
            subpackages.add(p.name)
    return subpackages


def get_spec_directories(specs_dir: Path) -> list[tuple[str, str, int]]:
    """Return a list of (dir_name, base_name, number) for specs."""
    specs = []
    if not specs_dir.exists():
        return specs

    pattern = re.compile(r"^(\d+)-(.*)$")
    for p in specs_dir.iterdir():
        if p.is_dir():
            match = pattern.match(p.name)
            if match:
                num = int(match.group(1))
                base_name = match.group(2)
                specs.append((p.name, base_name, num))
    return specs


def get_feature_files(features_dir: Path) -> set[str]:
    """Return a set of feature base names without the .feature extension."""
    features = set()
    if not features_dir.exists():
        return features

    for p in features_dir.rglob("*.feature"):
        features.add(p.stem)
    return features


def _print_gap_report(
    missing_specs: list[tuple[str, str]],
    orphaned_specs: list[str],
    missing_features: list[tuple[str, str]],
) -> None:
    """Print the gap analysis report in markdown format."""
    print("# Spec Gap Analysis Report\n")

    if missing_specs:
        print("## Missing Specs")
        print("The following `alos/` subpackages do not have corresponding specs:")
        for sp, suggestion in missing_specs:
            print(f"- `{sp}` (Suggested directory: `specs/{suggestion}/`)")
        print("")

    if orphaned_specs:
        print("## Orphaned Specs")
        print("The following spec directories do not match any `alos/` subpackage:")
        for s in orphaned_specs:
            print(f"- `{s}/`")
        print("")

    if missing_features:
        print("## Missing Features")
        print("The following spec directories lack corresponding `.feature` files:")
        for spec_dir, expected_feature in missing_features:
            print(f"- `{spec_dir}/` (Expected feature: `{expected_feature}`)")
        print("")


def main() -> None:
    alos_dir = Path("alos")
    specs_dir = Path("specs")
    features_dir = Path("tests/features")

    subpackages = get_alos_subpackages(alos_dir)
    specs = get_spec_directories(specs_dir)
    features = get_feature_files(features_dir)

    spec_base_names = {s[1] for s in specs}
    highest_spec_num = max([s[2] for s in specs], default=0)

    missing_specs = []
    for sp in subpackages:
        if not any(sp in base_name for base_name in spec_base_names):
            highest_spec_num += 1
            missing_specs.append((sp, f"{highest_spec_num:02d}-{sp}"))

    orphaned_specs = []
    for full_name, base_name, _num in specs:
        if not any(sp in base_name for sp in subpackages):
            orphaned_specs.append(full_name)

    missing_features = []
    for full_name, base_name, _num in specs:
        if base_name not in features:
            missing_features.append((full_name, f"{base_name}.feature"))

    has_gaps = bool(missing_specs or orphaned_specs or missing_features)

    if has_gaps:
        _print_gap_report(missing_specs, orphaned_specs, missing_features)
        sys.exit(0)
    else:
        print("No gaps found. Subpackages, specs, and features are fully aligned.")
        sys.exit(1)


if __name__ == "__main__":
    main()
