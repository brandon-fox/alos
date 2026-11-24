"""Unit tests for PR-05 provenance, workflow, speckit, crew, and telemetry domain models.

Spec: specs/036-hexagonal-twelve-factor-refactor/spec.md (FR-3603, FR-3604)
Constitution: Article I (Pydantic v2 Validation), Article III (Provenance), Article IV (TDD)
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from alos.domain.models import speckit, telemetry
from alos.domain.models.audit import AuditEvent, DecisionRecord
from alos.domain.models.crew import CrewAgentSpec, CrewTaskSpec
from alos.domain.models.evaluation import EvaluationResult, RiskLevel
from alos.domain.models.workflow import N8nExecutionResponse


def _assert_rejected_attr(obj: Any, attr: str, value: Any) -> None:
    with pytest.raises(ValidationError):
        setattr(obj, attr, value)


def _assert_invalid_payload(model_cls: type[BaseModel], payload: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        model_cls.model_validate(payload)


def test_evaluation_and_provenance_models_frozen() -> None:
    """Verify EvaluationResult, DecisionRecord, and AuditEvent immutability and schemas."""
    r1 = EvaluationResult(valid=True, critique="VALID", risk_level=RiskLevel.HIGH)
    r2 = EvaluationResult(valid=False, critique="Violation")
    assert r1.preferences_checked is not r2.preferences_checked
    assert r1.corrections_checked is not r2.corrections_checked
    assert r2.risk_level is RiskLevel.LOW and r2.requires_approval is False
    _assert_rejected_attr(r1, "valid", False)
    _assert_invalid_payload(EvaluationResult, {"valid": True, "critique": "ok", "extra": 1})

    rec = DecisionRecord(
        decision_id="D-007",
        trigger="Send email",
        action_type="email_send",
        risk_level=RiskLevel.HIGH,
        decision="APPROVED",
        rationale="Approved by human gate.",
        constitution_articles_checked=["I §1", "V"],
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
        span_id="00f067aa0ba902b7",
    )
    assert rec.risk_level is RiskLevel.HIGH and rec.self_correction_rounds == 0
    _assert_rejected_attr(rec, "rationale", "mutated")
    _assert_invalid_payload(
        DecisionRecord,
        {"action_type": "email_send", "risk_level": "HIGH", "decision": "BAD", "rationale": "x"},
    )

    ev1 = AuditEvent(step="MCP Execution", status="SUCCESS", metadata={"ok": True})
    ev2 = AuditEvent(step="Context Assembly", status="SUCCESS")
    assert ev1.metadata is not ev2.metadata
    _assert_rejected_attr(ev1, "status", "FAILED")
    _assert_invalid_payload(AuditEvent, {"step": "x", "status": "OK", "extra_key": 1})


def test_workflow_speckit_and_crew_models_frozen() -> None:
    """Verify workflow, speckit, and crew models preserve fields and enforce immutability."""
    resp = N8nExecutionResponse(status_code=200, data={"ok": True}, execution_id="e1", error=None)
    assert (resp.status_code, resp.execution_id, resp.error) == (200, "e1", None)
    _assert_rejected_attr(resp, "status_code", 500)
    _assert_invalid_payload(N8nExecutionResponse, {"status_code": 200, "unknown": 1})

    assert issubclass(speckit.InvalidStateTransitionError, ValueError)
    lifecycle = speckit.LifecycleRecord(feature_name="034-hexagonal")
    archive = speckit.ArchiveEntry(
        feature_name="034-hexagonal", original_path="specs/034", archive_path="specs/archive/034"
    )
    assert lifecycle.current_state is speckit.LifecycleState.DRAFT
    assert archive.state_at_archive is speckit.LifecycleState.ARCHIVED
    _assert_rejected_attr(lifecycle, "current_state", speckit.LifecycleState.APPROVED)
    _assert_rejected_attr(archive, "feature_name", "other")

    agent = CrewAgentSpec(role="Architect", goal="Design", backstory="Experienced")
    task = CrewTaskSpec(description="Plan", expected_output="Markdown", agent="Architect")
    assert task.agent == "Architect"
    _assert_rejected_attr(agent, "role", "Other")
    _assert_invalid_payload(
        CrewTaskSpec, {"description": "P", "expected_output": "M", "agent": "A", "x": 1}
    )


def test_telemetry_models_and_w3c_span_assignment_validation() -> None:
    """Verify TelemetryMetric is frozen and SpanContext validates live span updates."""
    metric = telemetry.TelemetryMetric(metric_name="latency_ms", value=12.5)
    _assert_rejected_attr(metric, "value", 1.0)
    _assert_invalid_payload(
        telemetry.TelemetryMetric, {"metric_name": "m", "value": 1.0, "extra": True}
    )
    summary = telemetry.HistogramSummary(
        count=1, sum=12.5, min=12.5, max=12.5, p50=12.5, p95=12.5, p99=12.5, buckets={"25": 1}
    )
    assert summary.count == 1
    _assert_rejected_attr(summary, "count", 2)

    tid, psid = "4bf92f3577b34da6a3ce929d0e0e4736", "00f067aa0ba902b7"
    assert telemetry.parse_traceparent(f"00-{tid}-{psid}-01") == (tid, psid)
    assert telemetry.parse_traceparent(f"00-{'0' * 32}-{psid}-01") is None
    assert telemetry.parse_traceparent("invalid") is None

    span = telemetry.SpanContext(
        trace_id=tid, span_id="1111222233334444", parent_span_id=psid, name="op", start_time=10.0
    )
    span.status, span.end_time, span.duration_ms, span.error = "SUCCESS", 10.5, 500.0, None
    span.add_event("checkpoint", {"items": 2})
    assert span.traceparent == f"00-{tid}-1111222233334444-01" and len(span.events) == 1
    _assert_rejected_attr(span, "duration_ms", "not-a-float")
    _assert_rejected_attr(span, "unknown_attr", "bad")
