"""Unit tests for the local swarm dispatcher (specs/029-local-swarm-dispatcher).

No test here needs Ollama, a GPU or the network: the model client is a fake.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from alos.swarm import dispatcher
from alos.swarm.dispatcher import Run, SwarmError, Worker

SCHEMA = {
    "type": "object",
    "required": ["title", "status"],
    "properties": {
        "title": {"type": "string", "maxLength": 10},
        "status": {"type": "string", "enum": ["draft", "done"]},
        "count": {"type": "integer"},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
}
ROSTER = {"classes": {"extract": {"model": "small", "slots": 2}, "hard": {"model": "big"}}}


class FakeOllama:
    """Returns queued responses; an exception in the queue is raised instead."""

    host = "http://fake"

    def __init__(self, replies: list[Any]) -> None:
        self.replies = list(replies)
        self.bodies: list[dict[str, Any]] = []

    def call(self, path: str, body: dict[str, Any] | None = None, timeout: float = 10.0) -> Any:
        self.bodies.append(body or {})
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(reply, BaseException):
            raise reply
        return reply


def answer(payload: Any, done_reason: str = "stop") -> dict[str, Any]:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return {"response": text, "done_reason": done_reason, "eval_count": 7}


@pytest.fixture
def run_dir(tmp_path: Path) -> Path:
    (tmp_path / "out").mkdir()
    (tmp_path / "prompt.md").write_text("Index this.", encoding="utf-8")
    (tmp_path / "input.txt").write_text("Status: Draft", encoding="utf-8")
    (tmp_path / "schema.json").write_text(json.dumps(SCHEMA), encoding="utf-8")
    return tmp_path


def job(job_id: str = "j1", job_class: str = "extract") -> dict[str, Any]:
    return {
        "id": job_id,
        "class": job_class,
        "input": "input.txt",
        "prompt": "prompt.md",
        "schema": "schema.json",
    }


def worker(run_dir: Path, replies: list[Any], thinking: bool = False) -> Worker:
    client: Any = FakeOllama(replies)
    return Worker(client, {"model": "small"}, run_dir, thinking)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ({"title": "ok", "status": "draft"}, None),
        ({"title": "ok"}, "$: missing required key 'status'"),
        ({"title": "ok", "status": "planned"}, "$.status: must be one of ['draft', 'done']"),
        ({"title": "x" * 11, "status": "done"}, "$.title: longer than 10 characters"),
        ({"title": "ok", "status": "done", "count": True}, "$.count: expected integer"),
        ({"title": "ok", "status": "done", "tags": ["a", 2]}, "$.tags[1]: expected string"),
        (["not", "an", "object"], "$: expected object"),
    ],
)
def test_schema_errors_reports_the_first_violation(value: Any, expected: str | None) -> None:
    assert next(dispatcher.schema_errors(value, SCHEMA), None) == expected


def test_judge_treats_a_capped_answer_as_failed_not_short() -> None:
    output, err = dispatcher.judge(answer('{"title": "cut', "length"), SCHEMA)
    assert output is None
    assert err == "output hit the token cap before finishing"


def test_judge_rejects_non_json_and_empty_text() -> None:
    assert dispatcher.judge(answer("not json"), SCHEMA)[1] == "output is not valid JSON"
    assert dispatcher.judge(answer("   "), None)[1] == "empty output"
    assert dispatcher.judge(answer(" fine "), None) == ("fine", None)


def test_run_job_ok_writes_the_result_envelope(run_dir: Path) -> None:
    res = dispatcher.run_job(
        worker(run_dir, [answer({"title": "ok", "status": "draft"})]), job(), dispatcher.DEFAULTS
    )
    stored = json.loads((run_dir / "out" / "j1.json").read_text(encoding="utf-8"))
    assert res["status"] == "ok"
    assert stored["output"] == {"title": "ok", "status": "draft"}
    assert stored["attempts"] == 1


def test_run_job_retries_once_with_the_validation_error_appended(run_dir: Path) -> None:
    w = worker(run_dir, [answer({"title": "ok"}), answer({"title": "ok", "status": "done"})])
    res = dispatcher.run_job(w, job(), dispatcher.DEFAULTS)
    client: Any = w.client
    assert res["status"] == "ok"
    assert res["attempts"] == 2
    assert "missing required key 'status'" in client.bodies[1]["prompt"]


def test_run_job_escalates_after_the_retry_budget(run_dir: Path) -> None:
    res = dispatcher.run_job(worker(run_dir, [answer({"title": "ok"})]), job(), dispatcher.DEFAULTS)
    assert res["status"] == "escalate"
    assert res["attempts"] == 2
    assert res["output"] is None


def test_run_job_records_a_timeout_without_retrying(run_dir: Path) -> None:
    res = dispatcher.run_job(
        worker(run_dir, [TimeoutError("timed out")]), job(), dispatcher.DEFAULTS
    )
    assert res["status"] == "timeout"
    assert res["attempts"] == 1


def test_run_job_escalates_when_the_input_file_is_missing(run_dir: Path) -> None:
    missing = {**job(), "input": "nope.txt"}
    res = dispatcher.run_job(worker(run_dir, [answer({})]), missing, dispatcher.DEFAULTS)
    assert res["status"] == "escalate"
    assert "could not read" in res["reason"]


def test_thinking_is_sent_as_false_only_when_the_model_supports_it(run_dir: Path) -> None:
    plain = dispatcher.request_body(worker(run_dir, []), "p", None, dispatcher.DEFAULTS)
    capable = dispatcher.request_body(worker(run_dir, [], True), "p", None, dispatcher.DEFAULTS)
    assert "think" not in plain
    assert capable["think"] is False
    assert plain["options"]["num_predict"] == dispatcher.DEFAULTS["max_tokens"]


def test_plan_phases_groups_by_model_in_roster_order(run_dir: Path) -> None:
    manifest = {"jobs": [job("b1", "hard"), job("a1"), job("a2")]}
    phases = dispatcher.plan_phases(Run(run_dir, manifest, ROSTER, run_dir), {"small", "big"})
    assert list(phases) == ["small", "big"]
    assert [j["id"] for j in phases["small"][1]] == ["a1", "a2"]


@pytest.mark.parametrize(
    ("bad_job", "installed", "message"),
    [
        (job("../escape"), {"small", "big"}, "must match"),
        (job("j1", "poetry"), {"small", "big"}, "not in the roster"),
        (job("j1"), {"big"}, "is not installed"),
    ],
)
def test_plan_phases_refuses_bad_manifests(
    run_dir: Path, bad_job: dict[str, Any], installed: set[str], message: str
) -> None:
    run = Run(run_dir, {"jobs": [bad_job]}, ROSTER, run_dir)
    with pytest.raises(SwarmError, match=message):
        dispatcher.plan_phases(run, installed)


def test_fan_out_aborts_when_the_first_ten_jobs_mostly_fail(run_dir: Path) -> None:
    jobs = [job(f"j{i:02d}") for i in range(25)]
    done, failed, aborted = dispatcher.fan_out(
        worker(run_dir, [answer("not json")]), jobs, {"retries": 0}, slots=1
    )
    assert aborted is True
    assert failed == done  # every job that ran failed
    assert 10 <= done < 25  # a job already picked up may finish; the rest never start


def test_resume_skips_jobs_with_an_ok_result_and_finish_counts_them(run_dir: Path) -> None:
    run = Run(run_dir, {"run_id": "r1", "jobs": [job("j1"), job("j2")]}, ROSTER, run_dir / "home")
    dispatcher.run_job(
        worker(run_dir, [answer({"title": "ok", "status": "done"})]), job("j1"), dispatcher.DEFAULTS
    )
    assert run.is_done(job("j1")) is True
    assert run.is_done(job("j2")) is False
    summary = run.finish("done", "")
    assert summary["counts"] == {"ok": 1, "not_run": 1}
    ledger = (run_dir / "home" / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(ledger[0])["run_id"] == "r1"


def test_gate_reports_a_listed_process_and_foreign_gpu_memory(monkeypatch: Any) -> None:
    client: Any = FakeOllama([{"models": [{"size_vram": 2 * 2**30}]}])
    monkeypatch.setattr(dispatcher, "running_processes", lambda: '"game.exe","123"')
    monkeypatch.setattr(dispatcher, "gpu_stats", lambda: (5, 9000, 16000))
    assert dispatcher.gate(client, ["Game.exe"], 4096) == "Game.exe is running"
    assert dispatcher.gate(client, [], 4096) == "GPU memory in use by other programs: 6952 MiB"
    assert dispatcher.gate(client, [], 8192) is None


def test_execute_reports_busy_before_anything_loads(run_dir: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(dispatcher, "gate", lambda *_: "Game.exe is running")
    run = Run(run_dir, {"jobs": [job()]}, ROSTER, run_dir)
    assert dispatcher.execute(run) == ("busy", "Game.exe is running")
