"""Property-based parser, schema, sandbox, and Python-vs-Rust differential fuzz suites.

Spec: specs/035-parallel-testing-and-qa-matrix/spec.md (FR-011)
ADR: ADR-0020
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from alos.core.config import ALOSConfig
from alos.core.evaluator import RiskLevel
from alos.logs.decision_log import DecisionLogger
from alos.logs.system_audit import SystemAuditLogger
from alos.memory.obsidian_graph import ObsidianGraphEngine
from alos.memory.obsidian_vault import ObsidianVaultParser
from alos.native import HAS_NATIVE_EXTENSION
from alos.native.fallback import (
    FallbackAuditJournalWriter,
    FallbackBM25Indexer,
    FallbackSafetyEvaluator,
)
from alos.schemas.actions import (
    ActionPlan,
    EmailDraft,
    GoogleCalendarEvent,
    TodoistTaskCreate,
    VaultNoteUpdate,
    WebSearchQuery,
)
from alos.swarm import dispatcher, sandbox

pytestmark = [pytest.mark.fuzz, pytest.mark.source]

SAFE_TEXT = st.text(
    alphabet=st.characters(blacklist_categories=["Cs"], blacklist_characters="\x00"),
    min_size=0,
    max_size=120,
)


@given(
    title=SAFE_TEXT.filter(lambda s: len(s.strip()) > 0),
    priority=st.integers(min_value=1, max_value=4),
    labels=st.lists(SAFE_TEXT, max_size=4),
    query=SAFE_TEXT,
)
def test_fuzz_pydantic_action_schemas_and_config_roundtrip(
    title: str, priority: int, labels: list[str], query: str
) -> None:
    """FR-011: Action schemas & ALOSConfig survive arbitrary Unicode JSON round-trips."""
    todo = TodoistTaskCreate(title=title, priority=priority, labels=labels)
    cal = GoogleCalendarEvent(
        title=title,
        start_time="2026-11-23T10:00:00",
        end_time="2026-11-23T11:00:00",
    )
    mail = EmailDraft(to_email="user@example.com", subject=title, body=query)
    note = VaultNoteUpdate(filename="note.md", content=query)
    search = WebSearchQuery(query=query)
    plan = ActionPlan(plan_id="p-1", goal=title, actions=[todo, cal, mail, note, search])

    dumped = plan.model_dump_json()
    restored = ActionPlan.model_validate_json(dumped)
    assert restored.goal == title
    assert len(restored.actions) == 5

    cfg = ALOSConfig(vault_dir=title, mock_mode=True)
    assert cfg.to_dict()["vault_dir"] == title


@given(step=SAFE_TEXT, reason=SAFE_TEXT, blob=SAFE_TEXT)
def test_fuzz_audit_and_decision_jsonl_serialization(
    tmp_path: Path, step: str, reason: str, blob: str
) -> None:
    """FR-011: Arbitrary newlines, quotes, and Unicode serialize into strictly 1 JSONL line."""
    audit_path = tmp_path / "fuzz_audit.jsonl"
    dec_path = tmp_path / "fuzz_dec.jsonl"
    audit = SystemAuditLogger(log_file_path=str(audit_path))
    dec = DecisionLogger(log_file_path=str(dec_path))

    audit.log_event(step=step or "s", status="OK", reason=reason, metadata={"blob": blob})
    dec.log_decision(
        trigger=step or "t",
        action=WebSearchQuery(query=blob),
        risk_level=RiskLevel.LOW,
        decision="APPROVED",
        rationale=reason,
        constitution_articles_checked=["I"],
        preferences_checked=[blob],
        corrections_checked=[],
        alternatives_considered=[],
        self_correction_rounds=0,
    )
    a_lines = audit_path.read_text(encoding="utf-8").splitlines()
    d_lines = dec_path.read_text(encoding="utf-8").splitlines()
    assert len(a_lines) >= 1 and json.loads(a_lines[-1])["metadata"]["blob"] == blob
    assert len(d_lines) >= 1 and json.loads(d_lines[-1])["rationale"] == reason


@given(
    frontmatter_block=st.sampled_from(
        [
            "",
            "---\ntags: [alpha, beta]\n---\n",
            "---\r\ntags: single_tag\r\n---\r\n",
            "---\n::invalid: yaml: [\n---\n",
            "---not-delimiter\n",
        ]
    ),
    body=SAFE_TEXT,
    link_target=st.from_regex(r"[A-Za-z0-9_-]{1,16}", fullmatch=True),
)
def test_fuzz_obsidian_vault_and_graph_parsers(
    tmp_path: Path, frontmatter_block: str, body: str, link_target: str
) -> None:
    """FR-011: ObsidianVaultParser & ObsidianGraphEngine never crash on malformed frontmatter."""
    vdir = tmp_path / f"v_{abs(hash((frontmatter_block, body, link_target))) % 100000}"
    vdir.mkdir(parents=True, exist_ok=True)
    note_a = vdir / "NoteA.md"
    note_b = vdir / f"{link_target}.md"
    note_a.write_text(
        f"{frontmatter_block}{body}\n[[{link_target}|Alias#Sec]] #tag1\n",
        encoding="utf-8",
    )
    note_b.write_text("Backlink [[NoteA]]", encoding="utf-8")

    parser = ObsidianVaultParser(vault_dir=str(vdir))
    notes = parser.parse_all()
    assert len(notes) >= 1

    graph = ObsidianGraphEngine(vault_dir=str(vdir))
    hood = graph.get_neighborhood("NoteA", depth=1)
    assert "NoteA" in hood.nodes and link_target in hood.nodes


@given(
    rel_attempt=st.sampled_from(
        [
            "../outside.py",
            "../../etc/passwd",
            "/abs/escape.py",
            "",
            "missing.py",
        ]
    ),
    code=st.sampled_from([None, 0, 1, 2, 5, 125, 126, 127]),
    passed_n=st.integers(min_value=0, max_value=50),
    failed_n=st.integers(min_value=0, max_value=50),
)
def test_fuzz_sandbox_path_traversal_mutate_and_classify(
    tmp_path: Path,
    rel_attempt: str,
    code: int | None,
    passed_n: int,
    failed_n: int,
) -> None:
    """FR-011: Sandbox rejects path traversal, comma mounts, and classifies pytest exit codes."""
    repo = tmp_path / "sb_repo"
    repo.mkdir(exist_ok=True)
    (repo / "ok.py").write_text("x = 1 + 2\n", encoding="utf-8")

    with pytest.raises(sandbox.SandboxError):
        sandbox.bind(Path("/bad,comma/path"), "/repo")

    changed, why = sandbox.mutant_source(
        repo, {"file": rel_attempt, "line": "x = 1 + 2", "mutated": "x = 1 - 2"}
    )
    assert changed is None and why == "not_found"

    # Syntax-invalid mutation must return ("None", "invalid")
    bad_syn, syn_why = sandbox.mutant_source(
        repo, {"file": "ok.py", "line": "x = 1 + 2", "mutated": "def broken(:"}
    )
    assert bad_syn is None and syn_why == "invalid"

    out_str = f"=== {passed_n} passed, {failed_n} failed in 0.12s ==="
    if code in sandbox.RUNTIME_FAILED:
        with pytest.raises(sandbox.SandboxError):
            sandbox.classify(code, out_str)
    else:
        res = sandbox.classify(code, out_str)
        assert res["state"] in {"timeout", "passed", "failed", "empty", "error"}


@given(
    payload=st.dictionaries(
        keys=st.sampled_from(["summary", "score", "items", "extra"]),
        values=st.one_of(st.text(max_size=20), st.integers(), st.booleans(), st.none()),
        max_size=4,
    )
)
def test_fuzz_dispatcher_schema_errors_and_judge(payload: dict[str, object]) -> None:
    """FR-011: dispatcher.schema_errors and judge validate arbitrary JSON objects safely."""
    schema = {
        "type": "object",
        "required": ["summary", "score"],
        "properties": {
            "summary": {"type": "string", "minLength": 1},
            "score": {"type": "integer"},
        },
        "additionalProperties": False,
    }
    errs = list(dispatcher.schema_errors(payload, schema))
    resp = {"response": json.dumps(payload), "done_reason": "stop"}
    parsed, reason = dispatcher.judge(resp, schema)
    if not errs:
        assert reason is None and parsed == payload
    else:
        assert reason is not None


@given(
    docs=st.lists(
        st.tuples(
            st.from_regex(r"[A-Za-z0-9 ]{0,25}", fullmatch=True),
            st.from_regex(r"[A-Za-z0-9 ]{0,60}", fullmatch=True),
            st.sampled_from(["spec", "vault"]),
        ),
        min_size=0,
        max_size=8,
    ),
    query=st.from_regex(r"[A-Za-z0-9 ]{0,25}", fullmatch=True),
    top_k=st.integers(min_value=1, max_value=6),
    source_filter=st.sampled_from([None, "spec", "vault"]),
    action_type=st.sampled_from(
        [
            "web_search",
            "todoist_create_task",
            "google_calendar_create_event",
            "vault_update_note",
            "email_send",
            "calendar_delete",
            "financial_transaction",
            "email_create_draft",
            "arbitrary_unknown_tool",
        ]
    ),
    hour=st.integers(min_value=0, max_value=23),
)
def test_differential_python_fallback_vs_native_contracts(
    tmp_path: Path,
    docs: list[tuple[str, str, str]],
    query: str,
    top_k: int,
    source_filter: str | None,
    action_type: str,
    hour: int,
) -> None:
    """FR-011: Differential fuzzing proving Fallback* invariants and Rust parity."""
    py_bm25 = FallbackBM25Indexer(k1=1.5, b=0.75)
    for idx, (hdr, body, stype) in enumerate(docs):
        py_bm25.add_chunk(hdr, f"f{idx}.md", f"/f{idx}.md", stype, body)
    py_hits = py_bm25.search(query, top_k=top_k, source_filter=source_filter)
    assert len(py_hits) <= top_k
    scores = [float(h["score"]) for h in py_hits]
    assert scores == sorted(scores, reverse=True)

    py_safe = FallbackSafetyEvaluator()
    prefs = ["No meetings scheduled after 5:00 PM"]
    corrs = ["Never book a flight without Delta"]
    ts = f"2026-11-23T{hour:02d}:30:00"
    py_risk = py_safe.classify_risk(action_type)
    py_cal = py_safe.validate_calendar_preferences(action_type, ts, prefs)
    py_corr = py_safe.validate_corrections(query, corrs)

    if HAS_NATIVE_EXTENSION:
        import alos_native  # type: ignore[import-not-found]  # optional compiled PyO3 extension

        rs_bm25 = alos_native.FastBM25Indexer(1.5, 0.75)
        for idx, (hdr, body, stype) in enumerate(docs):
            rs_bm25.add_chunk(hdr, f"f{idx}.md", f"/f{idx}.md", stype, body)
        rs_hits = rs_bm25.search(query, top_k, source_filter)
        assert len(rs_hits) == len(py_hits)
        for rh, ph in zip(rs_hits, py_hits, strict=True):
            assert math.isclose(float(rh["score"]), float(ph["score"]), rel_tol=1e-9, abs_tol=1e-12)

        rs_safe = alos_native.FastSafetyEvaluator()
        assert rs_safe.classify_risk(action_type) == py_risk
        assert dict(rs_safe.validate_calendar_preferences(action_type, ts, prefs)) == py_cal
        assert dict(rs_safe.validate_corrections(query, corrs)) == py_corr

        j_py = tmp_path / "j_py.jsonl"
        j_rs = tmp_path / "j_rs.jsonl"
        assert FallbackAuditJournalWriter(str(j_py)).append_record('{"ok":1}') is True
        assert alos_native.FastAuditJournalWriter(str(j_rs)).append_record('{"ok":1}') is True
        assert j_py.read_text(encoding="utf-8") == j_rs.read_text(encoding="utf-8")
