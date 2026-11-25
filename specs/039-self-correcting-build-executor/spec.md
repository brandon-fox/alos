# Feature Specification: Self-Correcting Build Executor

**Feature Branch**: `039-self-correcting-build-executor`

**Created**: 2026-11-24

**Status**: Approved

**Input**: User description: "An autonomous local-first build loop: ideas come from me, plus the existing specs that need building and refinement. Spec approval and merge approval are not hard gates; the goal is self-correction, with the test frame and First-ADE as the baseline for correctness. Update the manual blockers to allow for automation. The target state is tighter integration with n8n, LangGraph and CrewAI, but get the thing running as is for now."

**Builds on**: [029](../029-local-swarm-dispatcher/spec.md) (closes Task 13 merge cap and Task 14 First-ADE gate; uses Task 17's headless cloud lane), [030](../030-swarm-test-sandbox/spec.md) (container sandbox, mutants), [032](../032-preemptible-compute-governor/spec.md) (queue, governor, states), [037](../037-backlog-staging-and-burn/spec.md) (backlog harvester, hold latch, burn executor), [038](../038-enterprise-cicd-pipeline/spec.md) (`ci-merge-gate`). Constrained by issue #180 (stacked PRs and unsigned bot commits).

## Why

Spec 037 turns a backlog item into a Markdown deliverable that a person must read and apply by hand. Nothing on `main` applies a change, checks it, feeds the failure back and tries again. This spec adds that executor, so a backlog item can end as a merged, verified change without a person in the path, and a person sees only the items the loop could not make green.

Correctness is decided by evidence, not by approval: the repository's own test frame, a red-then-green check on the tests the change adds, a mutation check, the First-ADE compliance engines, and finally CI's `ci-merge-gate`. There is no standing human gate except for the files that define the gate itself (User Story 3).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A backlog item merges without me (Priority: P1)

As the maintainer, I want a queued `build` item that the baseline passes to end as a squash-merged change on `main`, so the backlog drains while I am away.

**Why this priority**: This is the loop. Without it every item still ends at a human.

**Independent Test**: Stage one LOW-risk `build` item against a fixture repository whose fix is known; run `alos burn --max-jobs 1`; verify a verified-signature PR against `main` opens, passes the baseline locally, and the job reaches `review_pending` with the PR number recorded.

**Acceptance Scenarios**:

1. **Given** a queued `build` item with a `source_ref` that resolves to a spec section and a clean worktree off `origin/main`, **When** the executor runs, **Then** it assembles context (the spec section, the target files, the repository's lint and test config), asks the `architect` tier for a unified diff, and applies it with `git apply --check` before writing anything.
2. **Given** an applied patch, **When** the baseline (FR-3904) passes, **Then** the executor creates the commit through the GitHub API (FR-3909) on branch `fix/loop-<job_id>` or `feat/loop-<job_id>` and opens a PR against `main` labelled `alos-loop`.
3. **Given** the PR's `ci-merge-gate` succeeds, **When** Auto Merge runs, **Then** the PR squash-merges and the job moves from `review_pending` to `succeeded` with the merge SHA recorded.

---

### User Story 2 - A red result corrects itself (Priority: P1)

As the maintainer, I want a failing attempt to be retried with its own failure output, and a stuck item to have its spec refined before it reaches me, so most red results become green without me.

**Why this priority**: Local models rarely get a change right first time; self-correction is what makes the loop worth running. Many existing specs are thin, so a repeated failure is often a spec problem, not a code problem.

**Independent Test**: Stage an item whose first model reply is scripted to fail one test and whose second passes; verify two attempts are recorded, the second prompt carries the first attempt's trimmed failure output, and only the second attempt is pushed.

**Acceptance Scenarios**:

1. **Given** an attempt fails any baseline step, **When** attempts remain, **Then** the next attempt starts from a fresh worktree at the same base and its prompt carries the failing step's name and trimmed output (FR-3906).
2. **Given** 3 local attempts have failed, **When** the item allows cloud overflow, **Then** one further attempt runs on the headless cloud lane with the same context and feedback.
3. **Given** every build attempt has failed, **When** the item has not been refined yet, **Then** the executor queues one `spec_refine` job that rewrites the item's spec section and tasks using the failure evidence, and then one more build attempt against the refined spec.
4. **Given** the refined attempt also fails, **When** the executor gives up, **Then** the job moves to `escalated`, no PR opens, the last worktree is kept, and one entry is written to the escalation list (FR-3911).
5. **Given** CI's `ci-merge-gate` fails on an opened PR, **When** the failure is read back, **Then** it counts as a failed attempt and feeds the next one, up to the same limits.

6. **Given** an item names one file and a test path, **When** triage runs, **Then** it is labelled `mechanical` from rules alone, with no model call, and gets 1 candidate per attempt (FR-3920).
7. **Given** an item has no testable acceptance, **When** triage runs, **Then** it is labelled `underspecified`, no build attempt runs, and the result is `refine_spec` so the item goes to `spec_refine` first.
8. **Given** an attempt's candidate 1 fails to apply and candidate 2 passes the baseline, **When** the attempt is recorded, **Then** it counts as one attempt with two candidates, and the passing diff is the one kept (FR-3921).
9. **Given** the triage model is unreachable or answers off-label, **When** triage runs, **Then** the item gets the default budget and the failure is recorded.

---

### User Story 3 - Risk sets the evidence bar, not a human gate (Priority: P2)

As the maintainer, I want riskier changes to need more evidence rather than my approval, and only the files that define correctness itself to wait for me, so autonomy covers CI and dependency work without letting the loop rewrite its own baseline.

**Why this priority**: The ALOS constitution (V) requires a risk tier for every action. Model-written workflow changes run with write tokens, and a recent local draft added unpinned actions, against spec 028; stronger automated checks address that without a person. A loop that can edit its own verifier has no baseline left, so those few files stay human.

**Independent Test**: Run the risk classifier (FR-3908) over fixture diffs touching each path class; verify the tier, the extra checks it requires, and the resulting PR label.

**Acceptance Scenarios**:

1. **Given** a diff touching only `alos/`, `tests/`, `docs/` (outside `docs/adr/`) or `specs/`, **When** the baseline passes, **Then** the tier is LOW and the PR is eligible for Auto Merge.
2. **Given** a diff touching `.github/workflows/`, `docs/adr/`, `pyproject.toml` dependencies, `uv.lock`, `Dockerfile*` or `crates/`, **When** the baseline passes, **Then** the tier is HIGH and the PR is eligible for Auto Merge only after the HIGH checks pass: workflow lint and audit (`actionlint`, `zizmor`), every action pinned to an existing SHA, `uv lock --check`, dependency review, and an `approve` verdict from a reviewer model of a different family than the author model.
3. **Given** a diff touching a PROTECTED path (`.specify/memory/constitution.md`, `.github/rulesets/`, `.github/CODEOWNERS`, or the executor's own baseline and risk configuration and module), **When** the baseline passes, **Then** the PR opens labelled `do-not-merge` and the item is written to the escalation list.

---

### User Story 4 - Main stays green (Priority: P2)

As the maintainer, I want a loop merge that breaks `main` to stop the loop, revert itself and resume on its own, so one bad merge cannot compound and the loop does not wait for me.

**Why this priority**: Auto Merge plus a weak test makes a red `main` possible; the loop must notice its own damage and recover from it.

**Independent Test**: Simulate a red Main Guardian result on a loop merge SHA; verify the hold latch engages, a revert PR opens against `main`, and the hold clears once `main` is green again.

**Acceptance Scenarios**:

1. **Given** a loop PR has merged, **When** the post-merge checks on `main` fail for that SHA, **Then** the executor engages the hold latch, opens a revert PR labelled `alos-loop`, and writes an escalation entry.
2. **Given** the hold was engaged by a red `main`, **When** the post-merge checks on `main` are green again, **Then** the hold clears and the loop continues; `alos resume` remains a manual override.

### Edge Cases

- The model returns prose or a diff that does not apply: the attempt fails at `apply` and its error is the feedback.
- A test fails, then passes on an unchanged rerun: rerun a failing test once before counting it red; record it as `flaky` in the attempt log.
- The governor preempts an attempt (spec 032): the attempt does not count; it restarts from a fresh worktree.
- `main` moves while an attempt runs: the PR is rebased by the signed rebase (spec 033); a conflict counts as a failed attempt.
- The `source_ref` does not resolve to a spec section: the item goes straight to `spec_refine` without a build attempt.
- GitHub is unreachable or the CLI token has expired: nothing is pushed; the job waits in `review_pending` with reason `push_unavailable` and retries on the next poll.
- A diff adds no tests: allowed only when it changes no executable code (docs, specs); otherwise the red-green step fails.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-3901**: System MUST add a `build` workflow type to the queue, distinct from spec 037's burn types, so existing Markdown deliverables keep their behaviour.
- **FR-3902**: Each attempt MUST run in a fresh git worktree at the item's base commit (`origin/main` when the item was leased) under `ALOS_HOME/worktrees/<job_id>/attempt-<n>`, and MUST NOT modify any other checkout.
- **FR-3903**: The executor MUST assemble context before calling a model: the spec section named by `source_ref`, the contents of the files the item targets (or the nearest matches found by search), the repository's lint and test configuration, and, from attempt 2, the previous attempt's feedback. Context MUST fit the tier's context window; what is cut MUST be recorded.
- **FR-3904**: The baseline MUST run, in order, and stop at the first failure:
  1. `apply`: the diff applies cleanly and touches only files inside the repository.
  2. `static`: the repository's lint and type checks (for ALOS: `ruff check alos tests`, `mypy alos tests`).
  3. `tests`: the repository's test suite with its CI coverage floor (for ALOS: `--cov-fail-under=90`).
  4. `red-green`: every test the diff adds or changes fails on the base commit and passes on the patch.
  5. `mutation`: at least one mutant of the changed source lines is killed by the suite (spec 030 mutant runner).
  6. `ade`: `ade-compliance check-all` on the changed package reports no new violations.
  7. `leak`: the diff, commit message and PR body contain no local paths, usernames, machine names or personal email addresses.
- **FR-3905**: Steps `static`, `tests`, `red-green` and `mutation` MUST run inside the spec 030 sandbox container (no network, read-only root, repository mounted read-only), because the code under test was written by a model.
- **FR-3906**: Feedback to the next attempt MUST name the failing step and carry its output trimmed to a configured budget, keeping the first error and its traceback.
- **FR-3907**: An item MUST have at most 3 local attempts (`max_attempts` = 3), then at most 1 cloud-lane attempt when `allow_cloud_overflow` is set, then 1 `spec_refine` job and 1 build attempt against the refined spec, then move to `escalated`.
- **FR-3908**: A risk classifier MUST assign LOW, HIGH or PROTECTED from the paths a diff touches (User Story 3). HIGH PRs MUST pass the HIGH checks before Auto Merge; PROTECTED PRs MUST carry `do-not-merge`. The path lists MUST live in configuration, and that configuration is itself PROTECTED.
- **FR-3909**: Commits MUST be created through the GitHub API (`createCommitOnBranch`) with the maintainer's existing CLI authentication, so GitHub signs them (verified signature, `gpgsig` present for First-ADE A7) and the author is the noreply identity, with no key material, passphrase or SSH agent on the host. Local SSH signing MAY be used instead when an agent holds the key.
- **FR-3910**: PRs MUST target `main` only (issue #180), use an allowed branch prefix (`fix/loop-<job_id>` or `feat/loop-<job_id>`), carry a Conventional Commits title, and list the attempt count and baseline results in the body.
- **FR-3911**: The executor MUST keep an escalation list (`ALOS_HOME/results/escalations.md`, mirrored to the vault Bus) with one entry per escalated item: the item, the failing step, the last output, the worktree path and the PR if any.
- **FR-3912**: At most 3 loop PRs per repository may be open at once, using the existing `requires_merge` cap; this closes spec 029 Task 13.
- **FR-3913**: After a loop PR merges, the executor MUST read the post-merge result for that SHA; a red result triggers User Story 4, and a later green result on `main` clears the hold it set.
- **FR-3914**: Every attempt MUST be recorded (`ALOS_HOME/results/<repo>/<job_id>/attempt-<n>.md`: model, context sizes, diff, each step's result and duration) and summarised in the burn digest.
- **FR-3915**: The constitution's principles IV and V MUST be amended through an ADR so that the baseline (FR-3904) and, for HIGH tier, the HIGH checks stand in for "Tests written, user approved" and for human approval; human approval remains required only for PROTECTED paths.
- **FR-3916**: The governor MUST attribute GPU memory that grows while the queue is loading its own model to the managed instance, so the loop does not preempt itself during a load. Until then, `ALOS_FOREIGN_VRAM_LIMIT_MB` is raised on the workstation (spec 037 FR-3704).
- **FR-3917**: Every model call MUST leave a trace: prompt tokens read, answer tokens written, characters of thinking, context size, whether the prompt plus the answer budget fits the context, and load, read and write times. The trace MUST be stored with the job result and appended to `ALOS_HOME/logs/generation_trace.jsonl`, including for a call that fails.
- **FR-3918**: Model calls MUST turn thinking off unless the job payload sets `think`, and a call that returns no answer text MUST fail the attempt, so it retries and then escalates, instead of succeeding.
- **FR-3919**: A review answer MUST be checked against the evidence it was given before it counts as done: every file it cites must exist, and the share of supplied claims it addresses and of citations that match supplied evidence lines MUST be recorded; an answer below the configured floor fails validation and is retried once.

- **FR-3920**: Before the first attempt a triage step MUST label the item and set its attempt budget. Rules read facts first (files named, test path present, acceptance criteria count, spec length, a failing test already named); a small model labels only what rules leave open. Labels: `mechanical` (one file, clear test), `multi_file`, `underspecified` (no testable acceptance), `risky` (touches a path the risk classifier would not call LOW). The label sets `attempts`, `candidates`, `plan_first` and `test_first`; `underspecified` MUST return `refine_spec` and run no build attempt. The label, the facts behind it and the budget MUST be recorded with the attempt records. A triage failure MUST fall back to the default budget, never block the item.
- **FR-3921**: An item MUST be allowed up to 5 local attempts, and each attempt MAY draw up to 3 candidate diffs, kept in order until one passes the baseline. Extra attempts and candidates are spent only against a verifier: a candidate that fails to apply or fails a step costs a candidate, not an attempt. Thinking MAY be turned on only for a retry whose feedback carries a failing test (FR-3918 otherwise holds).

### Key Entities

- **BuildItem**: a queue job of workflow type `build` with `source_ref`, target paths, base commit, attempt count, tier and risk.
- **Attempt**: one model call plus its baseline run: worktree, diff, step results, feedback produced.
- **BaselineResult**: per step: `passed`, `failed`, `flaky` or `skipped`, with duration and trimmed output.
- **Escalation**: an item the loop could not make green or may not merge alone, with the evidence needed to pick it up.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Of the first 20 `build` items, at least 5 merge with no human action.
- **SC-002**: 0 unverified commits and 0 PRs against a base other than `main` from the loop.
- **SC-003**: 0 leaks (FR-3904 step 7) reach a public branch, issue or PR.
- **SC-004**: A loop merge turns `main` red at most once in the first 20 items, and every such case opens a revert PR within one poll interval.
- **SC-005**: 100% of escalations carry the failing step, its output and a kept worktree.
- **SC-006**: 0 loop merges touch a PROTECTED path.

### Kill criteria

Judged by the maintainer, not monitored by the system: after 20 `build` items, if fewer than 5 merged without human hands, or a loop merge broke `main` more than once, stop the executor and return to manual SpecKit runs. Triage (FR-3920, FR-3921): on 5 real spec tasks, if the extra attempts and candidates do not turn at least 1 more item green than the 3-attempt default, or triage labels disagree with the maintainer's own label on more than 2 of 5, remove it.

## Target state

Phase 1 runs on what is installed today: the queue daemon, the burn executor's plumbing, the spec 030 sandbox and the `gh` CLI. The target state moves orchestration onto the frameworks ALOS already ships, without changing the baseline:

- **LangGraph**: the attempt cycle (assemble, propose, verify, reflect, retry, refine, escalate) becomes a state graph on the spec 014 pattern (`alos/engine/langgraph_n8n_loop.py`, `alos/application/use_cases/n8n_reflection_loop.py`: evaluate, refine, attempt cap), so each transition is typed, checkpointed and replayable.
- **CrewAI**: `spec_refine` runs the `speckit_architect` crew, and the HIGH-tier reviewer runs the `code_quality` crew, in place of single prompts (`alos/crews/`).
- **n8n**: n8n schedules runs, fans out across repositories, receives escalations and post-merge results by webhook, and keeps run history, calling ALOS through `alos/integrations/n8n_client.py` and an HTTP bridge to the queue (spec 036 T023). n8n never reimplements the queue or the baseline.
- **Hexagonal boundary**: the executor is an application use case behind spec 036 ports, so the LangGraph, CrewAI and n8n adapters replace phase 1 adapters without touching domain logic.

## Open questions (VERIFY, resolved by tests in the plan phase)

- **V1**: The full ALOS suite runs inside the sandbox `full` image with `--network none` and a read-only mount (pytest cache, coverage data and basetemp need a writable tmpfs).
- **V2**: `qwen3-coder:30b` with a context window of at least 16k tokens fits on the workstation GPU beside a normal desktop, or the governor's step-down picks a tier that does.
- **V3**: Resolved 2026-11-24: a commit created with `createCommitOnBranch` on a private probe repository came back `verified: true` (`reason: valid`), authored by the noreply identity, with a `gpgsig` header. No passphrase or agent was used.
- **V4**: Resolved 2026-11-24: the `pr-governance` branch rule accepts `fix/` and `feat/` prefixes; `alos-loop/` would be rejected.
- **V5**: The headless cloud lane from spec 029 Task 17 returns an applicable unified diff.
- **V6**: Whether `ade-compliance check-all` exits non-zero when violations exist (a clean run exits 0 and prints `Violations: 0`); until shown, the executor parses the count rather than trusting the exit code.
- **V7**: Resolved 2026-11-24: PR #253, created through the API, was squash-merged by Auto Merge about a minute after `ci-merge-gate` passed.
- **V8**: Resolved 2026-11-24: the governor preempted its own first job at load time (`foreign GPU memory 10371 MiB > 4608 MiB` while managed memory read 2107 MiB, because Ollama reports a model only after it has loaded); with the limit raised, jobs complete (FR-3916).
- **V9**: Resolved 2026-11-24: on the first review wave, 21 of 109 calls to a thinking-capable model returned no answer after spending the whole 2,000-token budget on thinking, and were recorded as succeeded. With `think` set to false the same model answers directly, and a model without a thinking mode accepts the flag (FR-3918).
- **V10**: Resolved 2026-11-24: a traced review call read 4,393 prompt tokens from a 13,991-character prompt and wrote 1,165 tokens in 35 seconds inside an 8,192-token context, so prompts at the 14,000-character budget are not truncated (FR-3917).

## Assumptions

- Ideas enter the queue from the maintainer (`alos enqueue`) or from the spec 037 harvester; the loop never invents items, though `spec_refine` may rewrite an existing item's spec section.
- n8n, LangGraph and CrewAI orchestration are phase 2 (Target state); phase 1 covers the executor only.
- The first repository is ALOS; others join once SC-001 holds there.
- Escalations are read from the escalation list and the burn digest; the loop creates no tasks in other systems.
