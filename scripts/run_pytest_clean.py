"""Execute pytest with a fresh per-invocation basetemp outside IDE-watched directories."""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import pytest


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="alos_pytest_"))
    try:
        return int(pytest.main([f"--basetemp={root / 'run'}", *sys.argv[1:]]))
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
