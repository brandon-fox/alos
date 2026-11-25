"""Scan the lines a diff adds for text that must not reach a public repository.

Generic patterns live here. Anything specific to one person (user name, machine names,
employer) is read from a private terms file under ``ALOS_HOME`` so it never lands in git.

Spec: specs/039-self-correcting-build-executor/spec.md (FR-3904 step 7)
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

# Built from parts so this file does not contain the strings it looks for.
_USERS = "Us" + "ers"
_HOME = "ho" + "me"
_MOUNT = "~/" + "mn" + "t/"
GENERIC: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("local path", re.compile(rf"[A-Za-z]:[\\/]{_USERS}[\\/]|/{_USERS}/|/{_HOME}/\w|{_MOUNT}")),
    ("personal email", re.compile(r"[\w.+-]+@(?:gmail|outlook|hotmail|yahoo|icloud)\.com", re.I)),
)


@dataclass(frozen=True)
class Finding:
    kind: str
    line: int
    text: str


def load_terms(path: Path) -> list[str]:
    """Read private terms, one per line; blank lines and ``#`` comments are ignored."""
    if not path.is_file():
        return []
    lines = (ln.strip() for ln in path.read_text(encoding="utf-8").splitlines())
    return [ln for ln in lines if ln and not ln.startswith("#")]


def added_lines(diff: str) -> list[tuple[int, str]]:
    """Return ``(line number in the diff, text)`` for every added line."""
    rows = []
    for number, raw in enumerate(diff.splitlines(), start=1):
        if raw.startswith("+") and not raw.startswith("+++"):
            rows.append((number, raw[1:]))
    return rows


def scan_diff(diff: str, terms: Sequence[str] = ()) -> list[Finding]:
    """List every added line that matches a generic pattern or a private term."""
    private = [(t, re.compile(rf"\b{re.escape(t)}\b", re.I)) for t in terms]
    found: list[Finding] = []
    for number, text in added_lines(diff):
        for kind, pattern in GENERIC:
            if pattern.search(text):
                found.append(Finding(kind, number, text.strip()[:60]))
        for term, pattern in private:
            if pattern.search(text):
                found.append(Finding("private term", number, term))
    return found


def describe(findings: Sequence[Finding]) -> str:
    """One line per finding, for feedback to the model; private terms are not echoed."""
    parts = []
    for f in findings:
        shown = "a private term" if f.kind == "private term" else repr(f.text)
        parts.append(f"line {f.line}: {f.kind} ({shown})")
    return "; ".join(parts)
