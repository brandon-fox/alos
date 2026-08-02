"""Unit and Integration Tests for ALOS Native Bridge & Fallbacks.

Spec: specs/002-rust-core-architectural-refactor/spec.md (FR-009)
"""

from __future__ import annotations

from pathlib import Path

from alos.native import get_bm25_indexer, get_journal_writer, get_safety_evaluator


def test_native_bridge_fallback_safety_evaluator() -> None:
    """Test safety evaluator risk classification and validation through native bridge."""
    evaluator = get_safety_evaluator()
    assert evaluator.classify_risk("web_search") == "LOW"
    assert evaluator.classify_risk("email_send") == "HIGH"
    assert evaluator.classify_risk("todoist_create_task") == "MEDIUM"
    assert evaluator.classify_risk("unknown_action") == "HIGH"

    res_pref = evaluator.validate_calendar_preferences(
        action_type="google_calendar_create_event",
        start_time="2026-08-02T18:00:00",
        preferences=["No meetings scheduled after 5:00 PM"],
    )
    assert res_pref["valid"] is False

    res_corr = evaluator.validate_corrections(
        query="book flight to Boston",
        corrections=["Always use Delta for flight bookings"],
    )
    assert res_corr["valid"] is False


def test_native_bridge_fallback_audit_journal_writer(tmp_path: Path) -> None:
    """Test journal writer record appending and file path handling."""
    log_path = str(tmp_path / "test_audit.jsonl")
    writer = get_journal_writer(log_path)
    assert writer.get_file_path() == log_path

    success = writer.append_record('{"step": "test", "status": "APPROVED"}')
    assert success is True

    content = Path(log_path).read_text(encoding="utf-8")
    assert "APPROVED" in content


def test_native_bridge_fallback_bm25_indexer() -> None:
    """Test BM25 indexer chunk addition and search querying."""
    indexer = get_bm25_indexer()
    indexer.add_chunk(
        header="Header",
        file_name="note.md",
        file_path="/path/note.md",
        source_type="vault",
        content="Important architecture decision",
    )
    results = indexer.search("architecture", top_k=1)
    assert len(results) == 1
    assert results[0]["file_name"] == "note.md"
    indexer.clear()
