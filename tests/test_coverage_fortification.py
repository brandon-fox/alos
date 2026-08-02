"""Stage 1 Test Coverage Fortification Suite.

Spec: specs/002-rust-core-architectural-refactor/spec.md (FR-001)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alos.core.config import ALOSConfig
from alos.core.context_assembler import ContextAssembler, ContextPayload
from alos.core.evaluator import RiskClassifier, RiskLevel
from alos.logs.telemetry import TelemetryTracer, global_tracer
from alos.schemas.actions import EmailDraft, WebSearchQuery


def test_telemetry_tracer_span_lifecycle() -> None:
    """Test telemetry span creation, context manager, metrics, and reset."""
    tracer = TelemetryTracer()
    assert len(tracer.get_spans()) == 0

    with tracer.span("test_operation", tags={"component": "core"}) as span:
        assert span.name == "test_operation"
        assert span.status == "RUNNING"
        assert span.tags["component"] == "core"

    spans = tracer.get_spans()
    assert len(spans) == 1
    assert spans[0].status == "SUCCESS"
    assert spans[0].duration_ms is not None
    assert spans[0].duration_ms >= 0

    metric = tracer.record_metric("test_latency", 1.25, unit="ms")
    assert metric.value == 1.25
    assert len(tracer.get_metrics()) == 1

    tracer.clear()
    assert len(tracer.get_spans()) == 0
    assert len(tracer.get_metrics()) == 0


def test_telemetry_tracer_handles_exceptions() -> None:
    """Test that tracer captures exception message in span status."""
    tracer = TelemetryTracer()

    with pytest.raises(ValueError, match="Span failure test"), tracer.span("failing_span"):
        raise ValueError("Span failure test")

    spans = tracer.get_spans()
    assert len(spans) == 1
    assert spans[0].status == "ERROR"
    assert spans[0].error == "Span failure test"


def test_global_tracer_instance() -> None:
    """Verify global tracer singleton instance is active."""
    with global_tracer.span("global_test_span"):
        pass
    assert len(global_tracer.get_spans()) > 0
    global_tracer.clear()


def test_alos_config_to_dict() -> None:
    """Test ALOSConfig serialization to dict."""
    config = ALOSConfig(mock_mode=True)
    cfg_dict = config.to_dict()
    assert isinstance(cfg_dict, dict)
    assert cfg_dict["mock_mode"] is True


def test_risk_classifier_fail_safe_defaults() -> None:
    """Test RiskClassifier fail-safe defaults for unknown actions."""
    classifier = RiskClassifier()
    search_action = WebSearchQuery(query="test", description="search")
    assert classifier.classify(search_action) == RiskLevel.LOW

    email_action = EmailDraft(to_email="test@example.com", subject="Sub", body="Body")
    assert classifier.classify(email_action) == RiskLevel.HIGH


def test_context_assembler_empty_vault(tmp_path: Path) -> None:
    """Test ContextAssembler behavior with non-existent vault path."""
    empty_dir = str(tmp_path / "empty_vault")
    assembler = ContextAssembler(vault_dir=empty_dir)
    payload = assembler.assemble_context("Hello")
    assert isinstance(payload, ContextPayload)
    assert payload.preferences == []
    assert payload.corrections == []


def test_cli_main_help_output(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test CLI main function when run without query argument."""
    from alos.cli import main

    monkeypatch.setattr("sys.argv", ["alos.cli"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "ALOS Runtime CLI" in captured.out


def test_cli_main_with_query(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Test CLI main function with crew command argument."""
    from alos.cli import main

    monkeypatch.setattr(
        "sys.argv", ["alos.cli", "crew", "run", "--name", "speckit_architect", "--goal", "test"]
    )
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "status" in captured.out or "crew" in captured.out or "goal" in captured.out


def test_scheduler_lifecycle(tmp_path: Path) -> None:
    """Test BackgroundScheduler start, sweep execution, and shutdown."""
    from alos.engine.scheduler import BackgroundScheduler

    vault_dir = str(tmp_path / "scheduler_vault")
    scheduler = BackgroundScheduler(vault_dir=vault_dir)
    scheduler.start()
    res = scheduler.run_morning_sweep()
    assert isinstance(res, dict)
    scheduler.shutdown()
