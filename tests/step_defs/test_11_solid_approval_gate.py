"""BDD step definitions for DualLoopOrchestrator and approval gate (Spec 036 PR-08)."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from pytest_bdd import given, scenarios, then, when

from alos.application import ports
from alos.application import use_cases as uc
from alos.core.graph import ALOSStateGraph

scenarios("../features/11_solid_approval_gate.feature")


@given("a mocked DualLoopOrchestrator with mocked ports and HIGH-risk approval gate")
def step_mocked_orch(bdd_context: dict[str, Any]) -> None:
    v, dl = MagicMock(spec=ports.VaultRepositoryPort), MagicMock(spec=ports.DecisionLoggerPort)
    v.read_profile.return_value, v.collect_wiki_links.return_value = {"name": "Alex"}, []
    v.read_list.return_value = ["No meetings scheduled after 5:00 PM"]
    mcp, gate = MagicMock(spec=ports.MCPGatewayPort), MagicMock(spec=ports.HumanApprovalGatePort)
    mcp.execute_tool.return_value = {"status": "SUCCESS"}
    c, p = uc.AssembleContextUseCase(v), uc.PlanActionUseCase()
    e, d = uc.EvaluateActionUseCase(decision_logger=dl), uc.DualLoopOrchestrator
    bdd_context["m"] = (d(c, p, e, mcp, gate), d(c, p, e, mcp, max_attempts=1), gate, mcp, dl)


@when("high-risk email actions and low-risk web search actions execute")
def step_run_mocked_orch(bdd_context: dict[str, Any]) -> None:
    o1, o2, gate, _, _ = bdd_context["m"]
    gate.request_approval.side_effect = [False, True]
    p0, p1 = o1.run("Send email Q3"), o1.run("Send email Q3")
    bdd_context["out"] = (p0, p1, o1.run("Search docs"), o2.run("Schedule meeting Team Sync"))


@then("unapproved HIGH-risk returns PENDING_APPROVAL while approved and LOW-risk succeed")
def step_verify_mocked_orch(bdd_context: dict[str, Any]) -> None:
    _, _, gate, mcp, dl = bdd_context["m"]
    p0, p1, low, fail = bdd_context["out"]
    assert p0["status"] == "PENDING_APPROVAL" and p0["result"] is None
    assert p1["status"] == low["status"] == "SUCCESS" and fail["status"] == "FAILED"
    assert fail["self_correction_attempts"] == 1 and dl.log_decision_record.call_count == 4
    assert gate.request_approval.call_count == mcp.execute_tool.call_count == 2


@given("a live temporary vault with ALOSStateGraph and real audit and decision loggers")
def step_live_graph(tmp_path: Path, bdd_context: dict[str, Any]) -> None:
    (tmp_path / "PREFERENCES.md").write_text("- No meetings scheduled after 5:00 PM\n", "utf-8")
    v, ap, dp = str(tmp_path), tmp_path / "a.jsonl", tmp_path / "d.jsonl"
    bdd_context["paths"], bdd_context["g"] = (ap, dp), ALOSStateGraph(v, str(ap), str(dp))


@when("a meeting query and an unapproved high-risk email query run end-to-end")
def step_run_live_graph(bdd_context: dict[str, Any]) -> None:
    g: ALOSStateGraph = bdd_context["g"]
    bdd_context["lr"] = (g.run("Schedule meeting Team Sync"), g.run("Send email summary"))


@then("the meeting self-corrects cleanly on disk while the email halts at PENDING_APPROVAL")
def step_verify_live_graph(bdd_context: dict[str, Any]) -> None:
    meet, mail = bdd_context["lr"]
    assert meet["status"] == "SUCCESS" and meet["self_correction_attempts"] >= 1
    assert meet["final_action"]["start_time"] == "2026-08-01T14:00:00"
    assert mail["status"] == "PENDING_APPROVAL" and mail["result"] is None
    assert all(len(p.read_text("utf-8").splitlines()) >= 3 for p in bdd_context["paths"])
