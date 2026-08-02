"""Tests for .github/scripts/spec_review.py."""

import importlib.util
from pathlib import Path

# Dynamically import spec_review from .github/scripts/spec_review.py
script_path = Path(__file__).parent.parent / ".github" / "scripts" / "spec_review.py"
spec = importlib.util.spec_from_file_location("spec_review", script_path)
assert spec is not None and spec.loader is not None
spec_review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(spec_review)


def test_make_progress_bar() -> None:
    """Test ASCII progress bar generation."""
    assert spec_review.make_progress_bar(0, 0) == "`[░░░░░░░░░░]` 0%"
    assert spec_review.make_progress_bar(5, 10) == "`[█████░░░░░]` 50%"
    assert spec_review.make_progress_bar(10, 10) == "`[██████████]` 100%"


def test_format_fr_summary() -> None:
    """Test requirement ID summary formatting."""
    assert spec_review.format_fr_summary([]) == "None"
    assert spec_review.format_fr_summary(["FR-001"]) == "1 (FR-001)"
    assert spec_review.format_fr_summary(["FR-001", "FR-002"]) == "2 (FR-001, FR-002)"
    fr_summary = spec_review.format_fr_summary(["FR-001", "FR-002", "FR-003", "FR-004"])
    assert fr_summary == "4 (FR-001..FR-004)"


def test_analyze_specs_and_generate_report(tmp_path: Path) -> None:
    """Test specs scanning and report generation using temporary directory."""
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()

    # Feature 001: complete
    f1 = specs_dir / "001-test-feature"
    f1.mkdir()
    (f1 / "spec.md").write_text("Requirements: FR-001, FR-002", encoding="utf-8")
    (f1 / "plan.md").write_text("Architecture plan", encoding="utf-8")
    (f1 / "tasks.md").write_text("- [x] Task 1\n- [x] Task 2", encoding="utf-8")

    # Non-spec directory
    personas = specs_dir / "personas"
    personas.mkdir()
    (personas / "persona.md").write_text("Persona details", encoding="utf-8")

    features, non_spec_dirs, metrics = spec_review.analyze_specs(specs_dir)

    assert len(features) == 1
    assert features[0]["name"] == "001-test-feature"
    assert features[0]["completed_tasks"] == 2
    assert features[0]["total_tasks"] == 2
    assert features[0]["status"] == "🎉 Complete"
    assert non_spec_dirs == ["personas"]

    report_md = spec_review.generate_report(features, non_spec_dirs, metrics)
    assert "SpecKit Specification Quality Audit" in report_md
    assert "Executive Summary Dashboard" in report_md
    assert "Specification Audit Matrix" in report_md
    assert "`001-test-feature`" in report_md
    assert "Excluded non-feature directory: `personas`" in report_md
