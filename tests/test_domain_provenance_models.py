"""RED-first unit tests for PR-05 provenance, workflow, speckit, crew, and telemetry models.

Spec: specs/034-hexagonal-twelve-factor-refactor/spec.md (FR-3403, FR-3404)
Constitution: Article I (Pydantic v2 Validation), Article III (Provenance), Article IV (TDD)
"""

from __future__ import annotations

from typing import Any

import pytest
from alos.domain.models.audit import AuditEvent, DecisionRecord
from alos.domain.models.crew import CrewAgentSpec, CrewTaskSpec
from alos.domain.models.evaluation import EvaluationResult, RiskLevel
from alos.domain.models.speckit import (
    ArchiveEntry,
    InvalidStateTransitionError,
    LifecycleRecord,
    LifecycleState,
)
from alos.domain.models.telemetry import (
    HistogramSummary,
    SpanContext,
    TelemetryMetric,
    parse_traceparent,
)
from alos.domain.models.workflow import N8nExecutionResponse
from pydantic import ValidationError


def _assert_rejected_attr(obj: Any, attr: str, value: Any) -> None:
    """Assert that setting an attribute raises Pydantic ValidationError."""
    with pytest.raises(ValidationError):
        setattr(obj, attr, value)


def test_evaluation_result_frozen_and_non_shared_defaults() -> None:
    """Verify EvaluationResult is frozen, rejects extras, and avoids mutable defaults."""
    r1 = EvaluationResult(
        valid=True, critique="VALID", risk_level=RiskLevel.HIGH, requires_approval=True
    )
    r2 = EvaluationResult(valid=False, critique="Violation")
    assert r1.preferences_checked is not r2.preferences_checked
    assert r1.corrections_checked is not r2.corrections_checked
    assert r1.requires_approval is True
    _assert_rejected_attr(r1, "valid", False)
    with pytest.raises(ValidationError):
        EvaluationResult.model_validate({"valid": True, "critique": "ok", "unknown_field": "x"})


def test_decision_record_and_audit_event_provenance_contracts() -> None:
    """Verify DecisionRecord and AuditEvent enforce Article III schemas and immutability."""
    record = DecisionRecord(
        decision_id="D-007",
        trigger="Send status update",
        action_type="email_send",
        risk_level=RiskLevel.HIGH,
        decision="APPROVED",
        rationale="Approved by human gate.",
        constitution_articles_checked=["I §1", "V"],
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
        span_id="00f067aa0ba902b7",
    )
    assert record.risk_level is RiskLevel.HIGH
    assert record.self_correction_rounds == 0
    _assert_rejected_attr(record, "rationale", "mutated")
    with pytest.raises(ValidationError):
        DecisionRecord.model_validate(
            {
                "action_type": "email_send",
                "risk_level": "HIGH",
                "decision": "PENDING",
                "rationale": "Invalid decision value",
            }
        )

    event = AuditEvent(step="MCP Execution", status="SUCCESS", metadata={"ok": True})
    other = AuditEvent(step="Context Assembly", status="SUCCESS")
    assert event.metadata is not other.metadata
    _assert_rejected_attr(event, "status", "FAILED")
    with pytest.raises(ValidationError):
        AuditEvent.model_validate({"step": "x", "status": "OK", "extra_key": 1})


def test_workflow_speckit_and_crew_models_frozen() -> None:
    """Verify workflow, speckit, and crew models preserve fields and enforce immutability."""
    resp = N8nExecutionResponse(
        status_code=200, data={"ok": True}, execution_id="exec-1", error=None
    )
    assert (resp.status_code, resp.execution_id, resp.error) == (200, "exec-1", None)
    _assert_rejected_attr(resp, "status_code", 500)

    assert issubclass(InvalidStateTransitionError, ValueError)
    lifecycle = LifecycleRecord(feature_name="034-hexagonal")
    assert lifecycle.current_state is LifecycleState.DRAFT
    archive = ArchiveEntry(
        feature_name="034-hexagonal",
        original_path="specs/034-hexagonal",
        archive_path="specs/archive/034-hexagonal",
    )
    assert archive.state_at_archive is LifecycleState.ARCHIVED

    agent = CrewAgentSpec(role="Architect", goal="Design", backstory="Experienced")
    task = CrewTaskSpec(description="Plan", expected_output="Markdown", agent="Architect")
    assert task.agent == "Architect"
    _assert_rejected_attr(agent, "role", "Other")
    with pytest.raises(ValidationError):
        CrewTaskSpec.model_validate(
            {"description": "Plan", "expected_output": "MD", "agent": "A", "bad": 1}
        )


def test_telemetry_models_and_w3c_span_assignment_validation() -> None:
    """Verify TelemetryMetric is frozen and SpanContext supports validated active span updates."""
    metric = TelemetryMetric(metric_name="latency_ms", value=12.5)
    _assert_rejected_attr(metric, "value", 1.0)
    summary = HistogramSummary(
        count=1, sum=12.5, min=12.5, max=12.5, p50=12.5, p95=12.5, p99=12.5, buckets={"25.0": 1}
    )
    assert summary.count == 1

    header = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    assert parse_traceparent(header) == ("4bf92f3577b34da6a3ce929d0e0e4736", "00f067aa0ba902b7")
    assert parse_traceparent("00-" + "0" * 32 + "-00f067aa0ba902b7-01") is None
    assert parse_traceparent("invalid") is None

    span = SpanContext(
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
        span_id="1111222233334444",
        parent_span_id="00f067aa0ba902b7",
        name="domain.check",
        start_time=10.0,
    )
    span.status = "SUCCESS"
    span.end_time = 10.5
    span.duration_ms = 500.0
    span.add_event("checkpoint", {"items": 2})
    assert span.traceparent == "00-4bf92f3577b34da6a3ce929d0e0e4736-1111222233334444-01"
    assert len(span.events) == 1
    _assert_rejected_attr(span, "duration_ms", "not-a-float")
    _assert_rejected_attr(span, "unknown_attr", "bad")
