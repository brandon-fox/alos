"""RED-first unit and integration tests for SpecKitFilesystemRepository and N8nSelfReflection."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from alos.adapters.outbound.audit import InMemoryTelemetryAdapter
from alos.adapters.outbound.integrations import N8nMockAdapter
from alos.adapters.outbound.speckit import SpecKitFilesystemRepository
from alos.application.ports.outbound import SpecKitRepositoryPort
from alos.application.use_cases.n8n_reflection_loop import N8nSelfReflectionUseCase, N8nTaskState
from alos.domain.models.speckit import LifecycleState
from alos.domain.models.workflow import N8nExecutionResponse
from alos.domain.services.lifecycle_fsm import SpecKitLifecycleFSM
from alos.engine.langgraph_n8n_loop import N8nSelfReflectionGraph


class _AuthThenRetryOrchestrator:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def trigger_workflow(self, payload: dict[str, Any]) -> N8nExecutionResponse:
        inner = dict(payload.get("payload", {}))
        self.calls.append(inner)
        if len(self.calls) == 1:
            return N8nExecutionResponse(status_code=401, error="Missing api_key")
        if len(self.calls) == 2:
            return N8nExecutionResponse(status_code=503, error="")
        return N8nExecutionResponse(status_code=200, data={"ok": True}, execution_id="e-ok")


def _state(wf: str, payload: dict[str, Any], max_attempts: int = 3) -> N8nTaskState:
    return N8nTaskState(
        task_id="t-1",
        workflow_id=wf,
        payload=payload,
        execution_output=None,
        evaluation_valid=False,
        critique="",
        attempt_count=0,
        max_attempts=max_attempts,
        status="",
        audit_logs=[],
    )


@pytest.mark.mocked
def test_speckit_filesystem_repository_roundtrip_and_corruption_fallback(tmp_path: Path) -> None:
    """Verify SpecKitFilesystemRepository load, save, slash normalization, and corrupt fallback."""
    repo = SpecKitFilesystemRepository(root_dir=tmp_path)
    assert isinstance(repo, SpecKitRepositoryPort)
    draft = repo.load_record("specs/036")
    assert draft.current_state == LifecycleState.DRAFT and draft.history[0]["state"] == "draft"
    approved = SpecKitLifecycleFSM.apply_transition(draft, "approved", reason="Reviewed")
    repo.save_record(approved)
    reloaded = repo.load_record("specs\\036")
    assert reloaded.current_state == LifecycleState.APPROVED
    assert len(reloaded.history) == 2
    bad_file = tmp_path / ".specify" / "lifecycle_records" / "corrupt.json"
    bad_file.write_text("{not valid json", encoding="utf-8")
    assert repo.load_record("corrupt").current_state == LifecycleState.DRAFT


@pytest.mark.mocked
def test_n8n_reflection_use_case_and_langgraph_facade() -> None:
    """Verify N8nSelfReflectionUseCase refinement strategies, telemetry, and LangGraph facade."""
    tracer = InMemoryTelemetryAdapter()
    uc = N8nSelfReflectionUseCase(orchestrator=N8nMockAdapter(), tracer=tracer)
    recovered = uc.run(_state("wf-health-poll-self-correct", {"force_db_fail": True}))
    assert recovered["status"] == "success" and recovered["evaluation_valid"] is True
    assert recovered["attempt_count"] == 3
    exhausted = uc.run(_state("wf-fail", {"force_fail": True}, max_attempts=2))
    assert exhausted["status"] == "failed_max_retries" and exhausted["attempt_count"] == 2

    custom = _AuthThenRetryOrchestrator()
    res = N8nSelfReflectionUseCase(orchestrator=custom).run(_state("wf-custom", {}, max_attempts=4))
    assert res["status"] == "success" and custom.calls[1].get("api_key") == "auto_refined_token_99"
    assert custom.calls[2].get("_retry_timestamp") == "refined"

    graph = N8nSelfReflectionGraph(mock_mode=True, tracer=tracer)
    graph_out = graph.run(
        {
            "task_id": "g-1",
            "workflow_id": "wf-health-poll-self-correct",
            "payload": {"force_db_fail": True},
            "execution_output": None,
            "evaluation_valid": False,
            "critique": "",
            "attempt_count": 0,
            "max_attempts": 3,
            "status": "",
            "audit_logs": [],
        }
    )
    assert graph_out["status"] == "success"
    assert (
        tracer.get_counter(
            "alos_n8n_workflow_attempts_total",
            labels={"workflow_id": "wf-health-poll-self-correct", "status": "200"},
        )
        >= 2
    )
