"""Triage labels and budgets (spec 039 FR-3920, FR-3921)."""

from __future__ import annotations

from alos.swarm.build.triage import BUDGETS, facts, rule_label, triage


def item(files: list[str], acceptance: str = "works") -> dict[str, object]:
    return {"id": "x", "title": "t", "acceptance": acceptance, "files": files}


def test_one_file_with_acceptance_is_mechanical_without_a_model_call() -> None:
    def boom(_p: str) -> str:
        raise AssertionError("rules should decide")

    budget, rec = triage(item(["a.py"]), boom)
    assert (budget.label, budget.candidates, rec["source"]) == ("mechanical", 1, "rules")


def test_three_code_files_get_more_attempts_candidates_and_a_plan() -> None:
    budget, _ = triage(item(["a.py", "b.py", "c.py"]))
    assert (budget.attempts, budget.candidates, budget.plan_first) == (5, 3, True)


def test_no_acceptance_and_no_test_is_underspecified() -> None:
    budget, _ = triage(item(["a.py"], acceptance=""))
    assert (budget.label, budget.route, budget.attempts) == ("underspecified", "refine_spec", 0)


def test_build_and_ci_paths_are_risky_and_test_first() -> None:
    budget, _ = triage(item([".github/workflows/ci.yml"]))
    assert (budget.label, budget.test_first) == ("risky", True)


def test_model_labels_what_rules_leave_open() -> None:
    open_item = item([])
    assert rule_label(facts(open_item)) == ""
    budget, rec = triage(open_item, lambda _p: "Multi_file.")
    assert (budget.label, rec["source"]) == ("multi_file", "model")


def test_off_label_or_failed_model_falls_back_to_the_default() -> None:
    open_item = item([])
    off, rec = triage(open_item, lambda _p: "banana split")
    assert off == BUDGETS["default"] and "off-label" in rec["note"]

    def down(_p: str) -> str:
        raise ConnectionError

    failed, rec2 = triage(open_item, down)
    assert failed == BUDGETS["default"] and "ConnectionError" in rec2["note"]
    assert triage(open_item)[0] == BUDGETS["default"]


def test_build_modules_alone_are_not_risky() -> None:
    budget, _ = triage(item(["alos/swarm/build/cap.py"]))
    assert budget.label == "mechanical"
    assert triage(item(["alos/templates/build/risk.json"]))[0].label == "risky"


def test_model_cannot_call_an_item_risky_without_a_risky_path() -> None:
    budget, rec = triage(item([]), lambda _p: "risky")
    assert budget.label == "default" and "without risky path" in rec["note"]
