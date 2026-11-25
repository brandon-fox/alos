"""Triage: label a build item and set how much iteration it gets before any attempt runs.

Rules read facts first; a small model labels only what the rules leave open. A failed or
off-label model answer falls back to the default budget and never blocks the item.

Spec: specs/039-self-correcting-build-executor/spec.md (FR-3920, FR-3921)
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

TEST_FILE = re.compile(r"(^|/)(tests?/|test_[^/]*\.py$|[^/]*_test\.py$)")
RISKY_PATH = re.compile(r"(^|/)(\.github/|[^/]*risk[^/]*\.json$)")
LABELS = ("mechanical", "multi_file", "underspecified", "risky")
MULTI_FILE_MIN = 3

Classify = Callable[[str], str]


@dataclass(frozen=True)
class Budget:
    label: str
    attempts: int
    candidates: int
    plan_first: bool = False
    test_first: bool = False
    route: str = "build"  # build, or refine_spec when the item must be rewritten first


BUDGETS = {
    "default": Budget("default", 3, 1),
    "mechanical": Budget("mechanical", 3, 1),
    "multi_file": Budget("multi_file", 5, 3, plan_first=True),
    "risky": Budget("risky", 5, 2, plan_first=True, test_first=True),
    "underspecified": Budget("underspecified", 0, 0, route="refine_spec"),
}


def facts(item: dict[str, Any]) -> dict[str, Any]:
    """What can be read off the item without a model."""
    files = [str(f) for f in item.get("files", [])]
    code = [f for f in files if not TEST_FILE.search(f)]
    return {
        "code_files": len(code),
        "test_files": len(files) - len(code),
        "has_acceptance": bool(str(item.get("acceptance", "")).strip()),
        "risky_path": any(RISKY_PATH.search(f) for f in files),
    }


def rule_label(f: dict[str, Any]) -> str:
    """Label from facts alone; empty when the rules leave it open."""
    if f["risky_path"]:
        return "risky"
    if not f["has_acceptance"] and not f["test_files"]:
        return "underspecified"
    if f["code_files"] >= MULTI_FILE_MIN:
        return "multi_file"
    if f["code_files"] == 1 and f["has_acceptance"]:
        return "mechanical"
    return ""


def _ask(item: dict[str, Any], f: dict[str, Any], classify: Classify) -> tuple[str, str]:
    prompt = (
        f"Label this build task with one word from: {', '.join(LABELS)}.\n"
        "mechanical: one file, clear test. multi_file: several files change together. "
        "underspecified: no testable acceptance. risky: touches CI, build or risk config.\n"
        f"Task: {item.get('title', '')}\nAcceptance: {item.get('acceptance', '')}\n"
        f"Facts: {f}\nAnswer with the label only."
    )
    try:
        answer = classify(prompt).strip().lower()
    except Exception as exc:
        return "", f"triage model failed: {type(exc).__name__}"
    word = re.sub(r"[^a-z_]", "", answer.split()[0]) if answer.split() else ""
    return (word, "") if word in LABELS else ("", f"off-label answer: {answer[:40]!r}")


def triage(item: dict[str, Any], classify: Classify | None = None) -> tuple[Budget, dict[str, Any]]:
    """Return the budget and the record of how it was chosen."""
    f = facts(item)
    label, note = rule_label(f), ""
    source = "rules"
    if not label and classify is not None:
        label, note = _ask(item, f, classify)
        source = "model"
    budget = BUDGETS.get(label, BUDGETS["default"])
    record = {"label": budget.label, "source": source if label else "default", "facts": f}
    if note:
        record["note"] = note
    return budget, {**record, "budget": asdict(budget)}
