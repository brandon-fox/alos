#!/usr/bin/env python3
"""
TODO Harvester

Scans alos/ and tests/ for TODO, FIXME, HACK, XXX, and NOSONAR markers.
Outputs results as JSON to stdout and markdown summary to stderr.
"""

import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

MARKERS = ["TODO", "FIXME", "HACK", "XXX", "NOSONAR"]
MARKER_PATTERN = re.compile(rf"\b({'|'.join(MARKERS)})\b", re.IGNORECASE)


def scan_file(file_path: Path) -> list[dict[str, Any]]:
    """Scan a single file for markers."""
    findings = []
    try:
        with open(file_path, encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                match = MARKER_PATTERN.search(line)
                if match:
                    marker = match.group(1).upper()
                    text = line.strip()
                    # Hash for deduplication
                    hash_str = f"{file_path}:{line_no}:{marker}"
                    hash_val = hashlib.sha256(hash_str.encode("utf-8")).hexdigest()

                    findings.append(
                        {
                            "file": str(file_path),
                            "line": line_no,
                            "marker": marker,
                            "text": text,
                            "hash": hash_val,
                        }
                    )
    except UnicodeDecodeError:
        # Skip binary files or non-utf-8 files
        pass
    except Exception as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)

    return findings


def main() -> None:
    directories_to_scan = [Path("alos"), Path("tests")]
    all_findings = []

    for directory in directories_to_scan:
        if not directory.exists():
            continue

        for file_path in directory.rglob("*.py"):
            all_findings.extend(scan_file(file_path))

    if all_findings:
        # Print JSON to stdout
        print(json.dumps(all_findings, indent=2))

        # Print Markdown summary to stderr
        marker_counts = defaultdict(int)
        file_counts = defaultdict(int)

        for finding in all_findings:
            marker_counts[finding["marker"]] += 1
            file_counts[finding["file"]] += 1

        print("## TODO Harvester Summary\n", file=sys.stderr)

        print("### Markers Count\n", file=sys.stderr)
        for marker, count in sorted(marker_counts.items()):
            print(f"- **{marker}**: {count}", file=sys.stderr)

        print("\n### Breakdown by File\n", file=sys.stderr)
        for file_path, count in sorted(file_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"- `{file_path}`: {count}", file=sys.stderr)

        sys.exit(0)
    else:
        print("No markers found.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
