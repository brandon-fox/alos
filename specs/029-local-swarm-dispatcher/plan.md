# Architecture & Implementation Plan: Local Swarm Dispatcher

**Feature Branch**: `feat/swarm-dispatcher`
**Status**: Stage 1 implemented; stage 2 planned

---

## Shape

Three tiers. The swarming lives entirely in the middle one.

```text
planner (a person or a cloud model)
  |  1. writes a run folder, starts one process
  |  2. later reads summary.json only
  v
alos.swarm.dispatcher            <- owns fan-out, phases, budgets, validation, ledger
  |  concurrent requests, one model loaded at a time
  v
Ollama (the normal server for serial phases; a dispatcher-owned server for parallel ones)
  workers: a prompt and one input file each
```

## Component matrix

```text
alos/swarm/
  __init__.py
  dispatcher.py          # stage 1: the whole dispatcher, standard library only
scripts/swarm/
  bench_slots.py         # measures tokens per second by slot count per roster model
tests/
  test_swarm_dispatcher.py   # unit tests with a fake model client; no GPU, no network
docs/
  swarm.md               # usage, roster, measurements, limits
specs/029-local-swarm-dispatcher/
  spec.md  plan.md  tasks.md
```

## Decisions

- **Standard library only.** The dispatcher must run on a machine where the full ALOS
  environment is not installed, and it adds no dependency for the supply-chain gates to watch.
- **A job names a class, not a model.** Changing which model serves a class is a roster edit;
  no manifest changes.
- **One dispatcher-owned server per phase.** A stock Ollama serves one request at a time.
  Changing that is a system setting; starting a second server on its own port with exactly the
  phase's slots is not, and extra slots were measured to cost GPU placement on large models.
- **Structured output is constrained twice.** The job's schema is passed to Ollama as `format`,
  and the reply is checked again locally against the same schema, because the retry needs a
  reason to hand back and a second server version may ignore keywords.
- **A small schema checker instead of a library.** type, enum, maxLength, required, properties
  and items cover result envelopes; anything richer belongs in a later stage with a dependency
  decision of its own.
- **Job ids are file names.** They are restricted to `[A-Za-z0-9._-]` before any file is
  written.
- **The ledger measures the machine, not a person.** One line per run now; hourly in stage 2.

## Stage 2 (not built)

A standing loop that pulls from a queue whenever the contention gate is open, an hourly
capacity ledger, a merge cap for work that opens pull requests, the First-ADE compliance check
as the acceptance gate for code changes, and a cloud overflow lane. See spec.md.

## Verification

- `pytest tests/test_swarm_dispatcher.py` covers the schema gate, the output cap, retry and
  escalation, timeout, resume, early abort, manifest refusal, the contention gate and the
  ledger line.
- The measurements in `docs/swarm.md` are from real runs on one machine; `bench_slots.py`
  reproduces the slot table.
- Not covered by automated tests: starting and stopping the dispatcher-owned server, and
  `nvidia-smi` parsing. Both were exercised by hand in the runs recorded in `docs/swarm.md`.
