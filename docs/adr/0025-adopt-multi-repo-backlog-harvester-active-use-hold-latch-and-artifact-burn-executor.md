# Adopt Multi-Repo Backlog Harvester Active-Use Hold Latch and Artifact Burn Executor

* Status: accepted
* Deciders: Brandon Fox
* Date: 2026-11-24

Technical Story: `specs/037-backlog-staging-and-burn/spec.md`

## Context and Problem Statement

`StickyEpochQueue` and `HostGovernor` (Specs 032 and 034) provide single-GPU model-epoch leasing and preemption, yet real-world multi-hour backlog execution across Brandon Fox's personal GitHub repositories (`alos`, `nectR`, `first-ade`, `vindicta-specs`) has failed for four structural reasons: (1) no multi-repo GitHub/SpecKit/OpenSpec harvester exists to build and deduplicate a 2-3 hour backlog while filtering bot noise and superseded PRs, (2) staging jobs while actively using the workstation lacks an explicit hold/idle-arm latch to guarantee zero model warm-up until the user steps away, (3) `ModelSpinner` fails with HTTP 404 instead of stepping down to installed `fallback_models` when primary tier tags (`gemma4:12b`, `qwen3-coder:30b`) are absent, and (4) `default_prompt_executor` writes 512-token raw text only into SQLite without producing structured Markdown deliverables, optional local git worktree draft branches, or a CLI review command to clear `review_pending` merge caps. How should ALOS harvest, stage-and-hold, and burn multi-repository backlogs reliably?

## Decision Drivers

* Zero-interference staging while actively using the workstation (`0 MiB` managed VRAM until explicit `resume` or uninterrupted `user_idle_seconds >= min_idle_s`).
* Multi-repository backlog ingestion across SpecKit (`specs/*/tasks.md`), OpenSpec (`openspec/changes/*/tasks.md`), GitHub Issues, and failing PRs with deterministic noise/duplicate filtering and offline bundled fallback.
* Resilient tier execution that steps down to installed `fallback_models` on missing primary tags (`HTTP 404`) and supports `--force` overrides when desktop apps hold elevated background VRAM.
* Concrete, human-reviewable burn deliverables (`~/.alos/results/<repo>/<job_id>.md`, `burn_digest.md`, optional isolated `git worktree` draft branches, and `alos review` state transitions).

## Considered Options

* Option 1: Integrated `MultiRepoBacklogBuilder` + file-backed `QueueHoldLatch` (`manual` & `idle_gate`) + resilient `ModelSpinner` fallback + `artifact_burn_executor` writing Markdown deliverables and optional git worktree branches
* Option 2: External cron scripts invoking Stage 1 `alos-dispatcher` over static per-repo JSON manifests
* Option 3: Direct autonomous push-and-PR mutation from local 7B/12B Ollama workers without local staging hold or review artifacts

## Decision Outcome

Chosen option: "Option 1: Integrated `MultiRepoBacklogBuilder` + file-backed `QueueHoldLatch` (`manual` & `idle_gate`) + resilient `ModelSpinner` fallback + `artifact_burn_executor` writing Markdown deliverables and optional git worktree branches", because it integrates directly with `StickyEpochQueue` epoch affinity, guarantees zero GPU disruption while staging at the desk, survives missing tier weights, and produces durable on-disk plans, patches, and worktree drafts without risking unreviewed external writes.

### Positive Consequences

* Allows `alos backlog stage` to populate 2-3 hours of prioritized, epoch-batched tasks across `alos`, `nectR`, `first-ade`, and `vindicta-specs` in `< 1s` from a bundled snapshot or live via `gh` CLI while holding execution until idle.
* Eliminates silent queue stalls caused by missing primary Ollama tags, `review_pending` 3-PR deadlocks, or cold-start model loads during active desktop sessions.
* Produces structured, traceable Markdown deliverables under `ALOS_HOME/results/<repo>/<job_id>.md` alongside `burn_digest.md` and optional isolated git worktree branches (`alos-burn/<job_id>`).

### Negative Consequences

* Adds `run/queue_hold.json` state coordination between CLI staging commands (`backlog stage`, `pause`, `resume`) and `ComputeRuntimeLoop.run_once()`.
* Bundled multi-repository snapshots require periodic refresh via `alos backlog build --live-gh` as upstream GitHub issues and specs evolve.

## Pros and Cons of the Options

### Option 1: Integrated `MultiRepoBacklogBuilder` + `QueueHoldLatch` + `artifact_burn_executor`

* Good, because sticky `model_tier` epochs (`fast_coder`, `reasoner`, `architect`) batch tasks across all four repositories without VRAM swap thrashing.
* Good, because `QueueHoldLatch` (`idle_gate` and `manual`) prevents cold-loading models while the user is typing while auto-arming seamlessly after hands-off idle time.
* Bad, because maintaining both live `gh` harvesting and an offline bundled JSON snapshot adds parser test surface.

### Option 2: External cron scripts invoking `alos-dispatcher`

* Good, because it requires no changes to `alos/swarm/queue.py`.
* Bad, because `alos-dispatcher` lacks resumable `checkpoint_ns` preemption, `idle_gate` hold latches, and cross-repo relational state tracking.

### Option 3: Unreviewed direct push-and-PR mutation from local Ollama workers

* Good, because completed jobs immediately appear on GitHub.
* Bad, because it violates ALOS Constitution Principle I (Plan/Draft -> Validate) and Spec 029 routing rules against unreviewed external writes by small local models.

## Links

* Refines [ADR-0015](0015-adopt-preemptible-host-governor-and-sticky-model-epoch-queue.md)
* Refines [ADR-0018](0018-adopt-dual-mode-portable-wheel-and-hardened-container-production-runtime.md)
