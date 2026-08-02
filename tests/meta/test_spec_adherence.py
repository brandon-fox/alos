"""Pytest meta test for SpecKit specification directory layout and ADR adherence."""

import re
from pathlib import Path

import pytest


@pytest.mark.meta
def test_spec_directory_structure_and_adr_links() -> None:
    repo_root = Path(__file__).resolve().parent.parent.parent
    specs_dir = repo_root / "specs"
    adr_dir = repo_root / "docs" / "adr"

    assert specs_dir.exists(), "specs/ directory must exist"

    allowed_non_spec_dirs = {"personas"}
    spec_dirs = [
        d for d in specs_dir.iterdir() if d.is_dir() and d.name not in allowed_non_spec_dirs
    ]

    assert len(spec_dirs) > 0, "At least one spec directory must exist under specs/"

    seen_numbers: dict[str, str] = {}
    errors: list[str] = []

    for d in spec_dirs:
        dir_name = d.name

        # 1. 3-digit NNN-feature format check
        match = re.match(r"^(\d{3})-[a-z0-9-]+$", dir_name)
        if not match:
            errors.append(f"Directory '{dir_name}' must follow 3-digit 'NNN-feature-name' format.")
            continue

        num = match.group(1)
        if num in seen_numbers:
            prev = seen_numbers[num]
            errors.append(
                f"Duplicate spec index '{num}' in '{dir_name}' (conflicts with '{prev}')."
            )
        else:
            seen_numbers[num] = dir_name

        # 2. Required files check
        required_files = ["spec.md", "plan.md", "tasks.md", "checklists/requirements.md"]
        for req_file in required_files:
            file_path = d / req_file
            if not file_path.exists():
                errors.append(f"Spec directory '{dir_name}' is missing required file '{req_file}'.")

        # 3. ADR Link verification
        spec_md = d / "spec.md"
        if spec_md.exists():
            content = spec_md.read_text(encoding="utf-8")
            adr_matches = re.findall(r"ADR[-\s]?(\d{4})", content)
            for adr_num in adr_matches:
                matching_adrs = list(adr_dir.glob(f"{adr_num}-*.md"))
                if not matching_adrs:
                    errors.append(
                        f"Spec '{dir_name}' references ADR {adr_num}, "
                        f"but no matching ADR file found in docs/adr/."
                    )

    assert not errors, "SpecKit adherence validation failed:\n" + "\n".join(errors)
