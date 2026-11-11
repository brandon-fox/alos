# Feature Specification: Local Swarm Dispatcher

**Feature Branch**: `feat/swarm-dispatcher`
**Created**: 2026-11-09
**Status**: Draft (stage 1 implemented and run; stage 2 specified, prototype run; stage 3 specified, prototype running)

---

## Intent

A planner plans once and judges once; the local machine does everything in between.

The planner is a person or a cloud model. It splits a task into independent jobs and writes a
run folder. The dispatcher fans those jobs across local Ollama models and writes one summary
file. The planner reads the summary, resolves the jobs that were escalated, and stops.

This only saves planner effort when inputs are large and outputs are small, because the planner
never reads the inputs. If the planner must read the inputs to plan the split, the task should
not be a run.

Three budgets keep it from overthinking:

- **Planner budget.** Two touches per run: start it, collect it. No polling, no reading every
  worker output, no re-planning mid-run.
- **Worker budget.** Hard caps on output tokens, wall-clock time and retries. Schema-bound
  output. Workers never talk to each other.
- **Build budget.** One module, one manifest format, one roster. Standard library only.

## What "swarm" means on one GPU

One mid-range GPU cannot hold several mid-size models at once. The swarm is many concurrent
requests against one loaded model, run in phases by model. It is not many different models
running side by side. Measurements are in [`docs/swarm.md`](../../docs/swarm.md).

## Contracts

**Job manifest** (`<run>/manifest.json`, written by the planner):

```json
{
  "run_id": "2026-11-09-a",
  "defaults": { "max_tokens": 600, "timeout_s": 90, "retries": 1, "think": false },
  "jobs": [
    { "id": "j01", "class": "extract",
      "input": "inputs/j01.txt",
      "prompt": "prompts/extract.md",
      "schema": "schemas/extract.json" }
  ]
}
```

A job names a class, never a model. Jobs are independent: no job reads another job's output.
A job id matches `^[A-Za-z0-9._-]+$`, because it becomes a file name.

**Result envelope** (`<run>/out/<id>.json` per job, plus one `<run>/summary.json`):

```json
{ "id": "j01", "status": "ok", "model": "qwen2.5-coder:7b-instruct", "attempts": 1,
  "tokens_out": 212, "seconds": 3.1, "reason": "", "input": "...", "output": { } }
```

`status` is `ok`, `escalate` or `timeout`. The summary carries counts per status, the
escalation list with reasons, per-phase timings, and the run state: `done`, `aborted`, `busy`
or `error`.

**Roster** (class to model, concurrent slots, context size). The default is in
`alos/swarm/dispatcher.py`; a `roster.json` in the swarm home overrides it.

## Stage 1: one run (implemented)

```gherkin
Feature: Dispatch
  Scenario: A planner hands off a run
    Given a run folder with manifest.json, prompts and input files
    When "python -m alos.swarm.dispatcher <run>" is started
    Then the dispatcher owns all fan-out, retries and validation
    And the planner makes no further call until it reads summary.json

  Scenario: Task is not worth a run
    Given a task with fewer than about 5 jobs, or jobs that need each other's results
    When the planner plans
    Then the planner does the task itself and no run is created

Feature: Swarm execution
  Scenario: Phases by model
    Given a manifest with jobs in several classes
    When the dispatcher runs
    Then it groups jobs by roster model, in roster order
    And runs one model phase at a time
    And sends as many concurrent requests as that phase's roster slots

  Scenario: Parallel slots without a system setting
    Given a phase with more than one slot
    When the phase starts
    Then the dispatcher starts its own Ollama server on its own port with exactly that many slots
    And stops that server and its child processes when the phase ends

  Scenario: Workers are offline and isolated
    Given any job
    When a worker is called
    Then it receives the prompt and its own input file only
    And it has no tools, no network and no view of other jobs

  Scenario: Resume
    Given a run that stopped partway
    When the same run folder is started again
    Then jobs with an existing "ok" result are skipped

Feature: Overthinking budgets
  Scenario: Output cap
    Given a job with max_tokens
    When the worker stops because it hit the cap
    Then the attempt counts as failed, not as a short answer

  Scenario: Wall clock
    Given a job with timeout_s
    When the request runs past it
    Then the dispatcher drops the request and records "timeout"

  Scenario: Schema gate
    Given a job that declares a schema
    When the output fails validation
    Then the dispatcher retries once with the validation error appended
    And a second failure sets status "escalate"

  Scenario: Thinking is off by default
    Given a roster model that reports a thinking capability
    When a job does not set think to true
    Then the dispatcher sends think false

  Scenario: The planner's own budget
    Given a finished run
    When the planner collects it
    Then it reads summary.json
    And opens individual outputs only for escalated jobs and at most 3 samples

Feature: Escalation
  Scenario: Escalate up, never sideways
    Given jobs with status "escalate" or "timeout"
    When the planner collects the run
    Then the planner resolves those jobs itself
    And they are never re-queued to a local model

  Scenario: Early abort
    Given more than 30% of the first 10 jobs in a phase fail
    When the dispatcher checks
    Then it stops the run with state "aborted"
    And the summary says the prompt or the model choice is wrong

Feature: GPU contention
  Scenario: The machine is in use
    Given a process named in the roster's gate is running
    Or GPU memory in use by other programs is above the gate's threshold
    When a run is started
    Then the dispatcher exits with state "busy" and loads nothing

Feature: Failure
  Scenario: Ollama is not serving
    Given the Ollama address does not answer
    When a run is started
    Then the dispatcher writes state "error" with a one-line reason and exits

  Scenario: A manifest is wrong
    Given a job with an unknown class, a model that is not installed, or an unsafe id
    When a run is started
    Then the dispatcher writes state "error" naming the job, before any model loads
```

## Stage 2: standing loop and capacity ledger (specified, not built)

The design is complete when the machine has useful work waiting during every idle hour. More
hardware is justified when that queue stops draining. Busy is not the measure: any loop can pin
a GPU. The measure is unmet demand.

| State | Signal | Meaning |
| --- | --- | --- |
| Starved | Gate open, queue empty | Not enough real work is defined |
| Saturated, draining | Busy whenever the gate is open; queue empties each week | One machine is the right size |
| Saturated, growing | Busy whenever the gate is open; oldest job waits longer each week | Case for more hardware, written from the ledger |

The standing queue holds two kinds of work. Only the first can saturate a machine, because the
second waits on a human review.

| Kind | Examples | Needs review | Limit |
| --- | --- | --- | --- |
| No-merge work | Indexing, embeddings, evals, traceability reports, summaries | No | None |
| Merge work | Fixes, tests and docs opened as pull requests | Yes | 3 open agent pull requests per repository |

```gherkin
Feature: Standing loop
  Scenario: Idle machine pulls work
    Given the contention gate is open and the queue is not empty
    When the dispatcher wakes
    Then it runs the next model phase and keeps pulling until the gate closes

  Scenario: Queue is empty
    Given the gate is open and nothing is queued
    When the dispatcher wakes
    Then it records "starved" in the ledger and sleeps

  Scenario: Merge cap
    Given a repository with 3 open agent pull requests
    When merge work for that repository reaches the front of the queue
    Then it is skipped and no-merge work continues

Feature: Acceptance gate for code changes
  Scenario: A worker proposes a change
    Given worker output that would become a code change
    When the dispatcher prepares it
    Then the First-ADE compliance check must pass before a pull request is opened

Feature: Lane overflow
  Scenario: Local lane is behind
    Given a job whose class allows a cloud lane has waited past its threshold
    When the dispatcher schedules it
    Then it goes to the cloud lane
    And the ledger counts it as overflow demand

Feature: Capacity ledger
  Scenario: Hourly line
    Given the standing loop is installed
    When an hour ends
    Then it appends one line: gate state, GPU utilisation, memory in use, jobs done,
      jobs waiting, oldest wait, jobs sent to overflow, jobs refused for memory

  Scenario: Hardware trigger
    Given two consecutive weeks where gate-open hours are at least 90% busy
    And the oldest no-merge job's wait has grown week over week, or jobs were refused for memory
    When the maintainer reads the ledger
    Then the hardware case is written from it
    And refused-for-memory means a larger card, growing wait means more cards
```

The ledger measures the machine. Nothing alerts; it is read when the answer is wanted.
Stage 1 already appends one ledger line per run.

## Stage 3: feeders and the vault bus (prototype running, not yet in this repository)

Stage 2's prototype loop drained its queue in one night and then logged "starved": the limit
was never the machine, it was defined work. Stage 3 defines that work as five standing
feeders, and adds one folder through which the local machine, a cloud planner and a
web-capable cloud lane exchange requests and results without calling each other.

A feeder is a script, not a model. It walks its inputs and queues one job for each input whose
content changed since that input last finished "ok". Feeding costs no planner tokens, so the
planner budget of stage 1 holds: the planner reads one digest and the escalations.

| # | Group | The feeder queues | Class | What comes out |
| --- | --- | --- | --- | --- |
| 1 | Brain | each changed note in the vault | `prose` | an index note: summary, tags, related notes by embedding similarity |
| 2 | Research | each piece of a web answer the cloud lane fetched | `prose` | claims, each with the source URL the answer gave |
| 3 | Task candidates | each changed note | `prose` | suggested actions with a done-when line, in one file |
| 4 | Code | each changed repository file: index, specification audit, review | `extract`, `hard` | an index store; high-risk claims and untestable specifications in the digest |
| 5 | Digest | each piece of a large local input that a request names | `prose` | a brief: summary, facts, anomalies |

**Routing rule, local first.** Work goes local when inputs are large, outputs are small, the
jobs are independent and a schema can check each result. Work that needs the web goes to the
cloud lane. Work that needs judgment across jobs, or a write to a system other people or other
tools read (a task manager, a pull request, a shared document), stays with the planner.

**Bus contract.** One folder in the vault, `Bus/`:

| Path | Written by | Holds |
| --- | --- | --- |
| `Requests/` | a person, the planner, the cloud lane | one note per request: frontmatter `lane` (`gemini` or `local`), `status`, and for `local` an `input` path; the body is the question |
| `Results/` | the nightly loop | one note per answered request, and one digest note per night that ran any job |
| `Candidates.md` | the nightly loop | task candidates, newest night first |
| `Index/` | the nightly loop | the vault index |

`status` moves `queued` to `fetched` or `running`, then to `done` or `failed: <reason>`.

```gherkin
Feature: Feeders
  Scenario: Only changed inputs are queued
    Given an input whose content hash equals the hash stored when it last finished "ok"
    When a feeder builds the night's queue
    Then no job is queued for that input

  Scenario: Nothing changed
    Given no feeder queued a job
    When the night ends
    Then no digest note is written

  Scenario: Feeders generate no drafts
    Given the code feeder
    When it builds the queue
    Then it queues index, specification audit and review jobs only
    And no test or code drafts are generated until existing drafts have been run

Feature: Vault bus
  Scenario: A web request
    Given a request note with lane "gemini" and status "queued"
    When the nightly loop starts
    Then the cloud lane's CLI answers it headless, in a read-only mode, with web search
    And the answer is cut into pieces that local workers distill into claims with sources
    And the result note keeps the raw answer below the claims

  Scenario: Cloud lane cap
    Given more than 5 queued web requests
    When the nightly loop starts
    Then 5 are fetched and the rest stay "queued" for the next night

  Scenario: Cloud lane is out of quota
    Given the cloud lane's CLI answers that its quota is reached
    When the nightly loop is fetching
    Then that request and the ones after it stay "queued"
    And the local groups run as usual

  Scenario: A local brief
    Given a request note with lane "local" and an input path
    When the path is inside the allowed roots and holds readable text
    Then each piece is briefed by a local worker and one brief note is written
    But a path outside the allowed roots sets status "failed" and queues nothing

  Scenario: Write boundary
    Given any local worker output
    When the loop writes it into the vault
    Then it writes under "Bus/" only
    And every note it writes says it is unreviewed local-model output

Feature: Task candidates
  Scenario: A candidate must quote its note
    Given a candidate whose quote is not found in the note it came from
    When the night is collected
    Then the candidate is dropped

  Scenario: Candidates are not tasks
    Given accepted candidates
    When the night is collected
    Then at most 15 new lines are added to "Candidates.md"
    And nothing is created in any task manager

Feature: Nightly loop
  Scenario: One night
    Given a scheduled start and a stop time
    When the loop starts
    Then it builds the queue, drains it through the stage 1 dispatcher, and collects
    And the gate, budgets and early abort are the dispatcher's, unchanged

  Scenario: A model left loaded in the stock server
    Given the stock Ollama server holds a model in GPU memory
    When the loop is about to drain
    Then it asks the stock server to unload it, so it does not read as foreign memory
```

**Measured on 2026-11-11.**

| Check | Result |
| --- | --- |
| Classify accuracy on 826 files, truth from path | `llama3.2` 49%, `qwen2.5-coder:7b` 84%: `classify` and `tag` moved to the 7B |
| Eval-facts, 150 jobs, all four fields correct | `llama3.2` 14%, `qwen2.5-coder:7b` 75% (31 s), `qwen3-coder:30b` 91% (97 s), `gemma4:12b` 96% (60 s, 4 slots): `gemma4:12b` takes the new `prose` class |
| Cloud lane headless (open item below) | Gemini CLI refuses personal Google accounts (`UNSUPPORTED_CLIENT`); Antigravity CLI `agy -p --mode plan --output-format json` answered a web question in 88 s with a parseable result |
| Trial night, 26 jobs across groups 1, 3, 4 and 5 | all "ok" in 88 s; index, candidates, brief and digest notes written. The group 2 fetch returned no answer, and a repeat call returned "Individual quota reached": group 2 is unproven |

The prototype is `feeders.py` and `nightly.py` beside the stage 2 prototype in the swarm home.
It moves into `alos/swarm/` once it has survived a week of nights.

### Stage 3 kill criteria

Judged by the maintainer at the weekly review after two weeks of nights; nothing monitors these.

- A group whose output was not opened or acted on in those two weeks is removed.
- Task candidates: fewer than 1 in 5 survive intake.
- Code: no pull request that started from swarm output has merged in 14 days.
- Research: the cloud lane's quota or headless mode cannot carry 5 requests a night.

## Out of scope

Workers with tools, worker-to-worker conversation, dependent jobs (a second manifest planned
after the first is collected covers this), a queue service, a database, a web UI, more than
one host.

## Open items

| Item | Test that closes it |
| --- | --- |
| Quality floor per class | 20 or more golden jobs with known answers per class; under 90% moves the class up one model |
| Detached run outlives the session that started it | Start a run detached, end the session, check that summary.json appears |
| A cloud lane can be driven headless | Closed 2026-11-11: see the stage 3 measurements |
| Whether `gemma4:12b` should also take `extract` and `hard` | It out-scored both current models on eval-facts; repeat on a prose golden set and on a review set before moving them |
| Cloud lane quota | A web request about the lane's own limits, answered through the bus; then 5 requests on one night |

## Kill criteria

Judged by the maintainer; nothing monitors these.

- After 3 real runs, planner effort on planning, collecting and escalations is not clearly
  below doing those tasks directly.
- Escalation rate is above 30% on two runs in a row.
- The standing loop is starved on most gate-open hours for two weeks: there is no case for more
  hardware yet.
