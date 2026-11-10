"""Step definitions for 05_audit_logging.feature."""

import json
from pathlib import Path
from typing import Any

from pytest_bdd import given, parsers, scenarios, then, when

from alos.logs.system_audit import SystemAuditLogger

scenarios("../features/05_audit_logging.feature")


@given(parsers.parse('an initialized System Audit Logger target file "{relative_path}"'))
def step_init_audit_logger(tmp_path: Path, bdd_context: dict[str, Any], relative_path: str) -> None:
    log_file = tmp_path / relative_path
    logger = SystemAuditLogger(log_file_path=str(log_file))
    bdd_context["log_file"] = log_file
    bdd_context["logger"] = logger


@when(parsers.parse('ALOS completes execution step "{step_name}" with status "{status}"'))
def step_log_step_success(bdd_context: dict[str, Any], step_name: str, status: str) -> None:
    logger: SystemAuditLogger = bdd_context["logger"]
    logger.log_event(step=step_name, status=status)


@when(
    parsers.parse(
        'ALOS completes execution step "{step_name}" with status "{status}" and reason "{reason}"'
    )
)
def step_log_step_reason(
    bdd_context: dict[str, Any], step_name: str, status: str, reason: str
) -> None:
    logger: SystemAuditLogger = bdd_context["logger"]
    logger.log_event(step=step_name, status=status, reason=reason)


@then(parsers.parse('"{relative_path}" contains valid JSONL records for each step'))
def step_verify_jsonl_records(bdd_context: dict[str, Any], relative_path: str) -> None:
    log_file: Path = bdd_context["log_file"]
    assert log_file.exists()
    lines = log_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) >= 2
    for line in lines:
        record = json.loads(line)
        assert isinstance(record, dict)


@then("every log entry includes timestamp, step name, and status")
def step_verify_fields(bdd_context: dict[str, Any]) -> None:
    log_file: Path = bdd_context["log_file"]
    lines = log_file.read_text(encoding="utf-8").strip().split("\n")
    for line in lines:
        rec = json.loads(line)
        assert "timestamp" in rec
        assert "step" in rec
        assert "status" in rec
