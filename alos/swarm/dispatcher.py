"""Local swarm dispatcher: flat fan-out of independent jobs across local Ollama models.

Spec: specs/029-local-swarm-dispatcher/spec.md (the spec is the source of truth).

A planner (a person or a cloud model) writes a run folder holding ``manifest.json``,
prompts, schemas and input files. This module does everything in between: it groups jobs
by model, runs one model phase at a time with that model's concurrent slots, enforces
output, time and retry budgets, validates structured output, and writes one
``summary.json``. Workers receive a prompt and one input file and nothing else.

Standard library only.

Usage:
    python -m alos.swarm.dispatcher <run folder> [--force]
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import subprocess  # nosec B404
import sys
import threading
import time
import urllib.request
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_HOST = os.environ.get("ALOS_SWARM_OLLAMA", "http://127.0.0.1:11434")
ABORT_SAMPLE = 10
ABORT_RATE = 0.30
ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
DEFAULTS: dict[str, Any] = {
    "max_tokens": 600,
    "timeout_s": 90,
    "retries": 1,
    "think": False,
    "max_input_chars": 24000,
}
JSON_TYPES: dict[str, type | tuple[type, ...]] = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
}
# Class -> model and concurrent slots. Override by placing roster.json in the swarm home.
# Slots and class placement were measured on one 16 GB GPU; see docs/swarm.md.
DEFAULT_ROSTER: dict[str, Any] = {
    "server_port": 11435,
    "gate": {"processes": [], "vram_mb": 4096},
    "classes": {
        "classify": {"model": "llama3.2:latest", "slots": 8, "num_ctx": 8192},
        "tag": {"model": "llama3.2:latest", "slots": 8, "num_ctx": 8192},
        "extract": {"model": "qwen2.5-coder:7b-instruct", "slots": 8, "num_ctx": 8192},
        "code": {"model": "qwen2.5-coder:7b-instruct", "slots": 8, "num_ctx": 8192},
        "rewrite": {"model": "qwen2.5-coder:7b-instruct", "slots": 8, "num_ctx": 8192},
        "hard": {"model": "qwen3-coder:30b", "slots": 1, "num_ctx": 8192},
    },
}


class SwarmError(Exception):
    """A manifest or roster problem that stops the run before any model is loaded."""


class Ollama:
    """Minimal client for the local Ollama HTTP API."""

    def __init__(self, host: str = DEFAULT_HOST) -> None:
        self.host = host

    def call(
        self, path: str, body: dict[str, Any] | None = None, timeout: float = 10.0
    ) -> dict[str, Any]:
        """POST ``body`` (or GET when it is None) and return the decoded JSON object."""
        if not self.host.startswith(("http://", "https://")):
            raise ValueError(f"Ollama host must be an http(s) URL, got {self.host!r}")
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        req = urllib.request.Request(self.host + path, data=data, headers=headers)  # noqa: S310
        # The scheme is checked above, so file:/ and custom schemes cannot reach urlopen.
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310  # nosec B310
            decoded: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
        return decoded


def gpu_stats() -> tuple[int, int, int] | None:
    """Return (utilisation %, used MiB, total MiB), or None when nvidia-smi is unavailable."""
    cmd = [
        "nvidia-smi",
        "--query-gpu=utilization.gpu,memory.used,memory.total",
        "--format=csv,noheader,nounits",
    ]
    try:
        out = subprocess.run(  # noqa: S603  # nosec B603
            cmd, capture_output=True, text=True, timeout=10, check=False
        )
        util, used, total = (int(x) for x in out.stdout.strip().splitlines()[0].split(","))
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return None
    return util, used, total


def running_processes() -> str:
    """Lower-cased process listing on Windows; empty where ``tasklist`` does not exist."""
    cmd = ["tasklist", "/FO", "CSV", "/NH"]
    try:
        out = subprocess.run(  # noqa: S603  # nosec B603
            cmd, capture_output=True, text=True, timeout=15, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.lower()


def gate(client: Ollama, processes: list[str], vram_mb: int) -> str | None:
    """Feature: GPU contention. Return why the machine is in use, or None when it is free."""
    listing = running_processes()
    for name in processes:
        if f'"{name.lower()}"' in listing:
            return f"{name} is running"
    stats = gpu_stats()
    if stats is None:
        return None
    ours = 0
    with contextlib.suppress(OSError, ValueError):
        loaded = client.call("/api/ps").get("models", [])
        ours = sum(int(m.get("size_vram", 0)) for m in loaded) // 2**20
    other = stats[1] - ours
    if other > vram_mb:
        return f"GPU memory in use by other programs: {other} MiB"
    return None


def schema_errors(value: Any, schema: dict[str, Any], path: str = "$") -> Iterator[str]:
    """Yield violations of a small JSON Schema subset.

    Supported keywords: type, enum, maxLength, required, properties, items.
    """
    kind = schema.get("type", "")
    expected = JSON_TYPES.get(kind)
    bool_as_number = isinstance(value, bool) and kind in ("integer", "number")
    if expected is not None and (not isinstance(value, expected) or bool_as_number):
        yield f"{path}: expected {kind}"
        return
    yield from _scalar_errors(value, schema, path)
    if isinstance(value, dict):
        yield from _object_errors(value, schema, path)
    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            yield from schema_errors(item, schema["items"], f"{path}[{i}]")


def _scalar_errors(value: Any, schema: dict[str, Any], path: str) -> Iterator[str]:
    """enum and maxLength."""
    if "enum" in schema and value not in schema["enum"]:
        yield f"{path}: must be one of {schema['enum']}"
    if isinstance(value, str) and len(value) > schema.get("maxLength", len(value)):
        yield f"{path}: longer than {schema['maxLength']} characters"


def _object_errors(value: dict[str, Any], schema: dict[str, Any], path: str) -> Iterator[str]:
    """required and properties."""
    for key in schema.get("required", []):
        if key not in value:
            yield f"{path}: missing required key '{key}'"
    for key, sub in schema.get("properties", {}).items():
        if key in value:
            yield from schema_errors(value[key], sub, f"{path}.{key}")


def judge(resp: dict[str, Any], schema: dict[str, Any] | None) -> tuple[Any, str | None]:
    """Return (output, error) for one model response. Error is None when it is accepted."""
    raw = str(resp.get("response", ""))
    if resp.get("done_reason") == "length":
        return None, "output hit the token cap before finishing"
    if schema is None:
        text = raw.strip()
        return text, None if text else "empty output"
    try:
        output = json.loads(raw)
    except ValueError:
        return None, "output is not valid JSON"
    return output, next(schema_errors(output, schema), None)


def is_timeout(exc: BaseException) -> bool:
    """True when a request failed because the wall-clock budget ran out."""
    reason = getattr(exc, "reason", None)
    return (
        isinstance(exc, TimeoutError) or isinstance(reason, TimeoutError) or "timed out" in str(exc)
    )


def read_json(path: Path) -> dict[str, Any]:
    """Read a JSON object, tolerating the UTF-8 BOM that Windows tools write."""
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8-sig"))
    return loaded


@dataclass
class Worker:
    """Everything one model phase needs to run a job."""

    client: Ollama
    entry: dict[str, Any]
    run_dir: Path
    thinking: bool


def load_job(
    run_dir: Path, job: dict[str, Any], cfg: dict[str, Any]
) -> tuple[str, dict[str, Any] | None, Path]:
    """Build the worker prompt: the job's prompt file plus its one input file."""
    prompt = (run_dir / job["prompt"]).read_text(encoding="utf-8-sig")
    source = Path(job["input"])
    source = source if source.is_absolute() else run_dir / source
    text = source.read_text(encoding="utf-8", errors="replace")[: int(cfg["max_input_chars"])]
    schema = read_json(run_dir / job["schema"]) if job.get("schema") else None
    return f"{prompt}\n\n--- INPUT ---\n{text}\n--- END INPUT ---", schema, source


def request_body(
    worker: Worker, prompt: str, schema: dict[str, Any] | None, cfg: dict[str, Any]
) -> dict[str, Any]:
    """One non-streamed generate request with the job's output cap applied."""
    body: dict[str, Any] = {
        "model": worker.entry["model"],
        "prompt": prompt,
        "stream": False,
        "keep_alive": "10m",
        "options": {
            "num_predict": int(cfg["max_tokens"]),
            "num_ctx": int(worker.entry.get("num_ctx", 8192)),
            "temperature": 0.2,
        },
    }
    if schema is not None:
        body["format"] = schema
    if worker.thinking:  # Scenario: Thinking is off by default.
        body["think"] = bool(cfg["think"])
    return body


def run_job(worker: Worker, job: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    """Feature: Overthinking budgets. One job: capped output, capped time, bounded retries."""
    res: dict[str, Any] = {
        "id": job["id"],
        "status": "escalate",
        "model": worker.entry["model"],
        "attempts": 0,
        "tokens_out": 0,
        "seconds": 0.0,
        "reason": "",
        "input": str(job.get("input", "")),
        "output": None,
    }
    started = time.time()
    try:
        base, schema, source = load_job(worker.run_dir, job, cfg)
        res["input"] = str(source)
    except (OSError, ValueError, KeyError) as exc:
        res["reason"] = f"could not read the job's files: {exc}"
        return save_result(worker.run_dir, res, started)
    note = ""
    for attempt in range(1, int(cfg["retries"]) + 2):
        res["attempts"] = attempt
        body = request_body(worker, base + note, schema, cfg)
        try:
            resp = worker.client.call("/api/generate", body, timeout=float(cfg["timeout_s"]))
        except (OSError, ValueError) as exc:
            timed_out = is_timeout(exc)
            res["status"] = "timeout" if timed_out else "escalate"
            res["reason"] = (
                f"no answer within {cfg['timeout_s']}s" if timed_out else f"request failed: {exc}"
            )
            break
        res["tokens_out"] += int(resp.get("eval_count", 0))
        output, err = judge(resp, schema)
        if err is None:
            res.update(status="ok", reason="", output=output)
            break
        res["reason"] = err
        note = f"\n\nYour previous answer was rejected: {err}. Answer again and fix that."
    return save_result(worker.run_dir, res, started)


def save_result(run_dir: Path, res: dict[str, Any], started: float) -> dict[str, Any]:
    """Write the result envelope for one job and return it."""
    res["seconds"] = round(time.time() - started, 1)
    out = run_dir / "out" / f"{res['id']}.json"
    out.write_text(json.dumps(res, indent=2), encoding="utf-8")
    return res


def stop_server(proc: subprocess.Popen[bytes] | None) -> None:
    """Stop the dispatcher's own Ollama server and its children.

    On Windows, ``terminate()`` ends only ``ollama serve`` and leaves its runner process
    holding GPU memory, so the whole process tree is killed.
    """
    if proc is None:
        return
    if os.name == "nt":
        cmd = ["taskkill", "/PID", str(proc.pid), "/T", "/F"]
        subprocess.run(  # noqa: S603  # nosec B603
            cmd, capture_output=True, timeout=30, check=False
        )
    else:
        proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()


def start_server(port: int, parallel: int) -> tuple[Ollama, subprocess.Popen[bytes] | None]:
    """Start an Ollama server on its own port with exactly ``parallel`` slots.

    The normal Ollama install serves one request at a time unless a system setting is
    changed. A dispatcher-owned server gets parallel slots without touching that setting.
    Returns the client and the process; the process is None when a server already listens.
    """
    client = Ollama(f"http://127.0.0.1:{port}")
    with contextlib.suppress(OSError, ValueError):
        client.call("/api/version", timeout=2)
        return client, None
    env = dict(
        os.environ,
        OLLAMA_HOST=f"127.0.0.1:{port}",
        OLLAMA_NUM_PARALLEL=str(parallel),
        OLLAMA_MAX_LOADED_MODELS="1",
    )
    # Fixed argument list, no shell; ollama is resolved from PATH like any CLI.
    proc = subprocess.Popen(  # nosec B603 B607
        ["ollama", "serve"],  # noqa: S607
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    for _ in range(40):
        with contextlib.suppress(OSError, ValueError):
            client.call("/api/version", timeout=1)
            return client, proc
        time.sleep(0.5)
    stop_server(proc)
    raise RuntimeError("the dispatcher's own Ollama server did not start")


@dataclass
class Run:
    """One run folder: its manifest, the roster in force and the results so far."""

    run_dir: Path
    manifest: dict[str, Any]
    roster: dict[str, Any]
    home: Path
    started: float = field(default_factory=time.time)
    phases: list[dict[str, Any]] = field(default_factory=list)

    @property
    def jobs(self) -> list[dict[str, Any]]:
        """The manifest's jobs."""
        jobs: list[dict[str, Any]] = self.manifest["jobs"]
        return jobs

    def result(self, job: dict[str, Any]) -> dict[str, Any] | None:
        """The stored result for a job, or None when it has not run."""
        path = self.run_dir / "out" / f"{job['id']}.json"
        return read_json(path) if path.exists() else None

    def is_done(self, job: dict[str, Any]) -> bool:
        """Scenario: Resume. A job with an ok result is never run again."""
        stored = self.result(job)
        return stored is not None and stored.get("status") == "ok"

    def finish(self, state: str, reason: str) -> dict[str, Any]:
        """Write summary.json, append one ledger line, and return the summary."""
        results = [r for r in (self.result(job) for job in self.jobs) if r is not None]
        counts: dict[str, int] = {}
        for res in results:
            counts[res["status"]] = counts.get(res["status"], 0) + 1
        counts["not_run"] = len(self.jobs) - len(results)
        not_ok = [r for r in results if r["status"] != "ok"]
        summary: dict[str, Any] = {
            "run_id": self.manifest.get("run_id", self.run_dir.name),
            "state": state,
            "reason": reason,
            "jobs": len(self.jobs),
            "counts": counts,
            "tokens_out": sum(int(r["tokens_out"]) for r in results),
            "seconds": round(time.time() - self.started, 1),
            "phases": self.phases,
            "escalations": [{k: r[k] for k in ("id", "status", "reason", "input")} for r in not_ok],
        }
        (self.run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        stats = gpu_stats() or (None, None, None)
        line = {
            "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
            "run_id": summary["run_id"],
            "state": state,
            "jobs": len(self.jobs),
            "ok": counts.get("ok", 0),
            "not_ok": len(not_ok),
            "tokens_out": summary["tokens_out"],
            "seconds": summary["seconds"],
            "gpu_util": stats[0],
            "vram_used_mb": stats[1],
        }
        self.home.mkdir(parents=True, exist_ok=True)
        with (self.home / "ledger.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(line) + "\n")
        return summary


def plan_phases(
    run: Run, installed: set[str]
) -> dict[str, tuple[dict[str, Any], list[dict[str, Any]]]]:
    """Group jobs by roster model, in roster order. A job names a class, never a model."""
    classes: dict[str, dict[str, Any]] = run.roster["classes"]
    phases: dict[str, tuple[dict[str, Any], list[dict[str, Any]]]] = {}
    for entry in classes.values():
        phases.setdefault(entry["model"], (entry, []))
    for job in run.jobs:
        job_id = str(job.get("id", ""))
        if not ID_PATTERN.match(job_id):
            raise SwarmError(f"job id {job_id!r} must match {ID_PATTERN.pattern}")
        entry_for_job = classes.get(str(job.get("class")))
        if entry_for_job is None:
            raise SwarmError(f"job {job_id} names class {job.get('class')!r}, not in the roster")
        if entry_for_job["model"] not in installed:
            raise SwarmError(f"roster model {entry_for_job['model']} is not installed")
        phases[entry_for_job["model"]][1].append(job)
    return phases


def fan_out(
    worker: Worker, todo: list[dict[str, Any]], defaults: dict[str, Any], slots: int
) -> tuple[int, int, bool]:
    """Run jobs with ``slots`` concurrent requests. Returns (done, failed, aborted)."""
    abort = threading.Event()

    def guarded(job: dict[str, Any]) -> dict[str, Any] | None:
        if abort.is_set():
            return None
        cfg = {**DEFAULTS, **defaults, **{k: job[k] for k in DEFAULTS if k in job}}
        return run_job(worker, job, cfg)

    done = failed = 0
    with ThreadPoolExecutor(max_workers=slots) as pool:
        for future in as_completed([pool.submit(guarded, job) for job in todo]):
            res = future.result()
            if res is None:
                continue
            done += 1
            failed += res["status"] != "ok"
            # Scenario: Early abort - more than 30% of the first 10 jobs in a phase fail.
            if done == ABORT_SAMPLE and failed / done > ABORT_RATE:
                abort.set()
    return done, failed, abort.is_set()


def run_phase(run: Run, entry: dict[str, Any], todo: list[dict[str, Any]]) -> int | None:
    """Run one model phase. Returns the failure count when it aborted early, else None."""
    model = str(entry["model"])
    slots = max(1, int(entry.get("slots", 1)))
    client, proc = Ollama(), None
    port = run.roster.get("server_port")
    if port and slots > 1:
        client, proc = start_server(int(port), slots)
    started = time.time()
    try:
        thinking = False
        with contextlib.suppress(OSError, ValueError):
            shown = client.call("/api/show", {"model": model})
            thinking = "thinking" in shown.get("capabilities", [])
        worker = Worker(client, entry, run.run_dir, thinking)
        done, failed, aborted = fan_out(worker, todo, run.manifest.get("defaults", {}), slots)
        with contextlib.suppress(OSError, ValueError):  # one model loaded at a time
            client.call("/api/generate", {"model": model, "keep_alive": 0}, timeout=30)
    finally:
        stop_server(proc)
    run.phases.append(
        {
            "model": model,
            "slots": slots,
            "jobs": done,
            "failed": failed,
            "seconds": round(time.time() - started, 1),
        }
    )
    return failed if aborted else None


def execute(run: Run, force: bool = False) -> tuple[str, str]:
    """Run every phase. Returns (state, reason); state is done, busy, aborted or error."""
    client = Ollama()
    gate_cfg = run.roster.get("gate", {})
    if not force:
        busy = gate(client, list(gate_cfg.get("processes", [])), int(gate_cfg.get("vram_mb", 4096)))
        if busy:
            return "busy", busy
    try:
        installed = {str(m["name"]) for m in client.call("/api/tags")["models"]}
        phases = plan_phases(run, installed)
    except (OSError, ValueError, KeyError) as exc:
        return "error", f"Ollama is not answering at {client.host}: {exc}"
    except SwarmError as exc:
        return "error", str(exc)
    for model, (entry, jobs) in phases.items():
        todo = [job for job in jobs if not run.is_done(job)]
        if not todo:
            continue
        try:
            failed = run_phase(run, entry, todo)
        except RuntimeError as exc:
            return "error", str(exc)
        if failed is not None:
            why = f"{failed} of the first {ABORT_SAMPLE} jobs on {model} failed"
            return "aborted", f"{why}: the prompt or the model choice is wrong"
    return "done", ""


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point. Exit code 0 only when the run state is done."""
    parser = argparse.ArgumentParser(description="Run one swarm manifest on local Ollama models.")
    parser.add_argument("run", help="run folder containing manifest.json")
    parser.add_argument("--force", action="store_true", help="skip the GPU contention gate")
    args = parser.parse_args(argv)

    run_dir = Path(args.run).resolve()
    home = Path(os.environ.get("ALOS_SWARM_HOME", str(Path.home() / "swarm")))
    roster_file = home / "roster.json"
    try:
        roster = read_json(roster_file) if roster_file.exists() else DEFAULT_ROSTER
        run = Run(run_dir, read_json(run_dir / "manifest.json"), roster, home)
    except (OSError, ValueError) as exc:
        print(f"cannot read the manifest or roster: {exc}", file=sys.stderr)
        return 2
    (run_dir / "out").mkdir(exist_ok=True)
    state, reason = execute(run, args.force)
    summary = run.finish(state, reason)
    keys = ("run_id", "state", "reason", "counts", "tokens_out", "seconds")
    print(json.dumps({k: summary[k] for k in keys}))
    return 0 if state == "done" else 1


if __name__ == "__main__":
    sys.exit(main())
