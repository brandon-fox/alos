"""RED-first unit tests for Ring 2 CQRS ports and core application use cases."""

from __future__ import annotations

from contextlib import nullcontext
from unittest.mock import MagicMock

import alos.domain.models.actions as act
from alos.application import ports
from alos.application import use_cases as uc
from alos.domain.models.context import ContextPayload, RAGDocument
from alos.domain.models.evaluation import RiskLevel


def test_core_use_cases_and_port_protocols() -> None:
    """AssembleContext, PlanAction, and EvaluateAction use pure ports and log DecisionRecords."""
    t = MagicMock(spec=ports.TelemetryPort)
    t.span.return_value = nullcontext()
    dlog = MagicMock(spec=ports.DecisionLoggerPort)
    vault = MagicMock(spec=ports.VaultRepositoryPort)
    p5, q = "No meetings scheduled after 5:00 PM", "Schedule meeting Team Sync"
    vault.read_profile.return_value = {"name": "Alex"}
    vault.read_list.side_effect = lambda f: [p5] if "pref" in f else []
    vault.collect_wiki_links.return_value = ["[[Projects]]"]
    mem = MagicMock(spec=ports.MemoryStorePort)
    mem.search.return_value = [RAGDocument(file_name="n", file_path="n", content="c", score=0.9)]
    c_uc, p_uc = uc.AssembleContextUseCase(vault, mem, t), uc.PlanActionUseCase(tracer=t)
    e_uc = uc.EvaluateActionUseCase(decision_logger=dlog, tracer=t)
    assert isinstance(t, ports.TelemetryPort) and isinstance(c_uc, ports.AssembleContextHandler)
    assert isinstance(p_uc, ports.PlanActionHandler)
    assert isinstance(e_uc, ports.EvaluateActionHandler)
    ctx = c_uc.execute(q)
    assert ctx.profile["name"] == "Alex" and len(ctx.rag_docs) == 1
    assert not uc.AssembleContextUseCase(vault).execute("hi").rag_docs
    bad = e_uc.execute(p_uc.execute(q, ctx), ctx, trigger="t1")
    assert not bad.valid and "5:00 PM" in bad.critique
    ok = e_uc.execute(p_uc.execute(q, ctx, bad.critique), ctx, trigger="t1")
    assert ok.valid and ok.risk_level == RiskLevel.MEDIUM and not ok.requires_approval
    empty = ContextPayload()
    hi = e_uc.execute(act.EmailSend(to_email="a@b.c", subject="Hi", body="Yo"), empty)
    calls = dlog.log_decision_record.call_args_list
    assert hi.requires_approval and len(calls) == 3 and t.span.call_count == 6
    assert calls[0].args[0].decision == "REJECTED" and calls[1].args[0].decision == "APPROVED"
    ev0 = uc.EvaluateActionUseCase()
    assert not ev0.execute(act.WebSearchQuery(query="q"), empty).requires_approval
