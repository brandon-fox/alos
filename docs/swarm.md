# Local swarm dispatcher

> **Status:** stage 1 (one run at a time) works and has been run on real inputs. Stage 2 (a
> standing loop and an hourly capacity ledger) is specified and not built. Stage 3 (five feeders
> and a vault folder that local models, a planner and a cloud lane share) is specified, with a
> prototype running outside this repository. Spec:
> [`specs/029-local-swarm-dispatcher/spec.md`](../specs/029-local-swarm-dispatcher/spec.md).

The dispatcher fans independent jobs out across local [Ollama](https://ollama.com) models. A
planner (you, or a cloud model) writes a run folder and reads one summary; the dispatcher does
everything in between. It uses the Python standard library only.

## Run it

```powershell
# a run folder holds manifest.json plus the prompt, schema and input files it names
python -m alos.swarm.dispatcher C:\path\to\runs\my-run
```

The last line printed is a one-line JSON summary. The exit code is 0 only when the run state is
`done`. Results are in `out/<job id>.json` and `summary.json` inside the run folder.

| Setting | Default | Purpose |
| --- | --- | --- |
| `ALOS_SWARM_HOME` | `~/swarm` | Holds `ledger.jsonl` and an optional `roster.json` override |
| `ALOS_SWARM_OLLAMA` | `http://127.0.0.1:11434` | The normal Ollama server, used for serial phases |
| `--force` | off | Skip the GPU contention gate |

## The roster

A job names a class; the roster maps a class to a model, a number of concurrent slots and a
context size. The default roster is `DEFAULT_ROSTER` in
[`alos/swarm/dispatcher.py`](../alos/swarm/dispatcher.py). To change it, put a `roster.json`
with the same shape in the swarm home:

```json
{
  "server_port": 11435,
  "gate": { "processes": ["Game.exe"], "vram_mb": 4096 },
  "classes": {
    "extract": { "model": "qwen2.5-coder:7b-instruct", "slots": 8, "num_ctx": 8192 },
    "hard":    { "model": "qwen3-coder:30b", "slots": 1, "num_ctx": 8192 }
  }
}
```

`gate.processes` lists programs that should keep the dispatcher off the GPU while they run.
Phases run in the order models first appear in `classes`.

## What was measured

One machine, 2026-11-09: RTX 5080 (16 GB), i9-14900KF, 64 GB RAM, Ollama 0.34.4, all models
Q4_K_M. These numbers set the default roster; rerun
[`scripts/swarm/bench_slots.py`](../scripts/swarm/bench_slots.py) on other hardware.

**A stock Ollama server runs one request at a time.** Sending 8 concurrent requests to the
normal server gave the same total throughput as sending 1 (about 295 tokens per second on
llama3.2, about 163 on qwen2.5-coder 7B). Concurrency there only queues.

**A dispatcher-owned server with parallel slots is where the swarm comes from.** Total tokens
per second, 200-token generations, server started with 8 slots:

| Model | 1 request | 2 | 4 | 8 | On GPU |
| --- | --- | --- | --- | --- | --- |
| llama3.2 (3.2B) | 300 | 520 | 748 | 1117 | 100% |
| qwen2.5-coder:7b-instruct | 159 | 48 (one stall) | 311 | 425 | 100% |
| qwen3-coder:30b | 60 | 85 | 88 | 95 | 57% |

The 30B model gains nothing from slots and loses GPU placement to them: with one slot it sits
74% on the GPU and runs at 95 tokens per second alone. So the dispatcher starts one server per
phase with exactly that phase's slots, and serial phases use the normal server.

**Small models fail quietly on extraction.** First real run: index 47 feature specifications
(about 3.7 KB each) into title, summary, status and open-question count. Every spec states
`Status: Draft`, which makes the status field a golden answer.

| Model | Slots | Wall time | Schema-valid on first try | Status correct |
| --- | --- | --- | --- | --- |
| llama3.2 (3.2B) | 8 | 13.8 s | 47 of 47 | 10 of 47 |
| qwen2.5-coder:7b-instruct | 8 | 17.7 s | 47 of 47 | 47 of 47 |
| qwen3-coder:30b | 1 | 48.3 s | 47 of 47 | 47 of 47 |

The 3B model returned well-formed JSON every time and was wrong about a field it could have
copied. A schema gate proves shape, not truth. The default roster therefore sends `extract` to
the 7B model and keeps the 3B model for `classify` and `tag`, which are not yet tested.

**Killing the server is not enough on Windows.** Terminating `ollama serve` left its runner
process alive holding 9.5 GB of GPU memory. The dispatcher kills the process tree, and the
contention gate caught the orphan on the next run (`busy`), which is how it was found.

## Limits

- Flat fan-out only. A job cannot read another job's output; plan a second run instead.
- Nothing checks that output is true. Sample it, or give a class a golden set.
- The gate's process check uses `tasklist`, so it only names programs on Windows. The GPU
  memory check works wherever `nvidia-smi` does.
- No embeddings class yet: it needs a different endpoint.
