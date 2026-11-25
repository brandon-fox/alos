"""Model-call trace, thinking switch and empty-answer failure for the queue executors.

Spec: specs/039-self-correcting-build-executor/spec.md (FR-3917, FR-3918)
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import pytest

from alos.runtime import RuntimePaths
from alos.swarm.burn import build_burn_executor
from alos.swarm.dispatcher import Ollama
from alos.swarm.queue import (
    EmptyResponseError,
    LeasedJob,
    PreemptedExecutionError,
    default_prompt_executor,
)

TRACE_FILE = "generation_trace.jsonl"
FULL: dict[str, Any] = {
    "response": " ok ",
    "eval_count": 1165,
    "prompt_eval_count": 4393,
    "done_reason": "stop",
    "load_duration": 5_000_000_000,
    "prompt_eval_duration": 2_100_000_000,
    "eval_duration": 28_100_000_000,
    "total_duration": 35_300_000_000,
}


class FakeOllama(Ollama):
    """Records generate bodies and replays one scripted answer."""

    def __init__(self, answer: dict[str, Any], context_length: int = 8192) -> None:
        super().__init__("http://127.0.0.1:1")
        self.answer = answer
        self.context_length = context_length
        self.bodies: list[dict[str, Any]] = []

    def call(
        self, path: str, body: dict[str, Any] | None = None, timeout: float = 10.0
    ) -> dict[str, Any]:
        if path == "/api/ps":
            if not self.context_length:
                return {"models": []}
            return {"models": [{"name": "gemma4:12b", "context_length": self.context_length}]}
        self.bodies.append(dict(body or {}))
        return dict(self.answer)


def make_job(payload: dict[str, Any], workflow: str = "smoke") -> LeasedJob:
    return LeasedJob(
        job_id="j-trace",
        repo_slug="alos",
        workflow_type=workflow,
        model_tier="reasoner",
        priority=50,
        requires_merge=False,
        allow_cloud_overflow=False,
        payload=payload,
        checkpoint_ns=None,
        state="leased",
        attempts=1,
        max_attempts=2,
    )


def read_trace(paths: RuntimePaths) -> list[dict[str, Any]]:
    text = (paths.logs_dir / TRACE_FILE).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines()]


def test_thinking_is_off_unless_the_payload_asks_for_it() -> None:
    client = FakeOllama(FULL)
    default_prompt_executor(make_job({"prompt": "hi"}), client, threading.Event())
    default_prompt_executor(make_job({"prompt": "hi", "think": True}), client, threading.Event())
    assert [body["think"] for body in client.bodies] == [False, True]


def test_result_carries_the_call_trace() -> None:
    job = make_job({"prompt": "hi", "max_tokens": 1800})
    res = default_prompt_executor(job, FakeOllama(FULL), threading.Event())
    assert res["response"] == "ok"
    assert res["trace"] == {
        "prompt_tokens": 4393,
        "answer_tokens": 1165,
        "thinking_chars": 0,
        "num_ctx": 8192,
        "num_predict": 1800,
        "fits_context": True,
        "load_ms": 5000.0,
        "prompt_ms": 2100.0,
        "answer_ms": 28100.0,
        "total_ms": 35300.0,
        "tokens_per_s": 41.5,
    }


@pytest.mark.parametrize(("prompt_tokens", "fits"), [(6392, True), (6393, False), (7000, False)])
def test_trace_says_whether_prompt_plus_answer_budget_fits(prompt_tokens: int, fits: bool) -> None:
    answer = {**FULL, "prompt_eval_count": prompt_tokens}
    job = make_job({"prompt": "hi", "max_tokens": 1800})
    res = default_prompt_executor(job, FakeOllama(answer), threading.Event())
    assert res["trace"]["fits_context"] is fits


def test_fit_is_unknown_without_a_context_and_speed_is_zero_without_timing() -> None:
    client = FakeOllama({"response": "ok", "thinking": "abc"}, context_length=0)
    res = default_prompt_executor(make_job({"prompt": "hi"}), client, threading.Event())
    trace = res["trace"]
    assert trace["num_ctx"] is None
    assert trace["fits_context"] is None
    assert trace["num_predict"] == 512
    assert trace["tokens_per_s"] == 0.0
    assert trace["thinking_chars"] == 3
    assert (trace["prompt_tokens"], trace["answer_tokens"], trace["total_ms"]) == (0, 0, 0.0)


def test_empty_answer_fails_the_attempt_and_reports_the_thinking() -> None:
    answer = {
        **FULL,
        "response": "  ",
        "thinking": "x" * 254,
        "eval_count": 2000,
        "done_reason": "length",
    }
    with pytest.raises(EmptyResponseError, match="254 characters of thinking") as err:
        default_prompt_executor(make_job({"prompt": "hi"}), FakeOllama(answer), threading.Event())
    assert not isinstance(err.value, PreemptedExecutionError)
    assert "2000 tokens generated" in str(err.value)
    assert "done_reason=length" in str(err.value)
    assert err.value.model == "gemma4:12b"
    assert err.value.trace["answer_tokens"] == 2000
    assert err.value.trace["thinking_chars"] == 254


def test_empty_answer_error_defaults_to_an_empty_trace() -> None:
    err = EmptyResponseError("no answer")
    assert err.trace == {}
    assert err.model == ""


def test_cancel_during_generation_still_preempts_before_the_empty_check() -> None:
    event = threading.Event()

    class Cancelling(FakeOllama):
        def call(
            self, path: str, body: dict[str, Any] | None = None, timeout: float = 10.0
        ) -> dict[str, Any]:
            out = super().call(path, body, timeout)
            if path == "/api/generate":
                event.set()
            return out

    with pytest.raises(PreemptedExecutionError):
        default_prompt_executor(
            make_job({"prompt": "hi"}), Cancelling({**FULL, "response": ""}), event
        )


def test_daemon_executor_appends_one_trace_line_per_real_call(tmp_path: Path) -> None:
    paths = RuntimePaths.resolve(str(tmp_path))
    run = build_burn_executor(paths=paths)
    run(make_job({"prompt": "hi"}), FakeOllama(FULL), threading.Event())
    burn = run(
        make_job({"prompt": "hi", "title": "T"}, "spec_audit"), FakeOllama(FULL), threading.Event()
    )
    lines = read_trace(paths)
    assert [(r["job_id"], r["workflow_type"], r["model_tier"], r["model"]) for r in lines] == [
        ("j-trace", "smoke", "reasoner", "gemma4:12b"),
        ("j-trace", "spec_audit", "reasoner", "gemma4:12b"),
    ]
    assert [
        (r["prompt_tokens"], r["answer_tokens"], r["answer_chars"], r["done_reason"]) for r in lines
    ] == [
        (4393, 1165, 2, "stop"),
        (4393, 1165, 2, "stop"),
    ]
    assert all(r["repo_slug"] == "alos" and r["at"] and r["fits_context"] is True for r in lines)
    header = Path(burn["artifact_path"]).read_text(encoding="utf-8")
    assert "tokens_out: 1165\ntokens_in: 4393\nseconds: 35.3\n" in header


def test_failed_empty_answer_is_traced_before_it_is_raised(tmp_path: Path) -> None:
    paths = RuntimePaths.resolve(str(tmp_path))
    run = build_burn_executor(paths=paths)
    answer = {**FULL, "response": "", "thinking": "abc"}
    with pytest.raises(EmptyResponseError):
        run(make_job({"prompt": "hi"}, "spec_audit"), FakeOllama(answer), threading.Event())
    (record,) = read_trace(paths)
    assert record["done_reason"] == "empty_answer"
    assert record["model"] == "gemma4:12b"
    assert record["thinking_chars"] == 3
    assert record["answer_chars"] == 0
    assert not list(paths.results_dir.glob("**/*.md"))


def test_mock_runs_and_untraced_results_leave_no_trace_file(tmp_path: Path) -> None:
    paths = RuntimePaths.resolve(str(tmp_path))
    run = build_burn_executor(paths=paths, mock_mode=True)
    run(make_job({"prompt": "hi"}), FakeOllama(FULL), threading.Event())
    mock = run(
        make_job({"prompt": "hi", "title": "T"}, "spec_audit"), FakeOllama(FULL), threading.Event()
    )
    assert not (paths.logs_dir / TRACE_FILE).exists()
    header = Path(mock["artifact_path"]).read_text(encoding="utf-8")
    assert "tokens_in: 0\nseconds: 0.0\n" in header
