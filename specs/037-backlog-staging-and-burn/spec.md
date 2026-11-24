# Feature Specification: Multi-Repo Backlog Harvester, Active-Use Hold Gate, and Verified Artifact Burn

**Feature Branch**: `037-backlog-staging-and-burn`

**Created**: 2026-11-24

**Status**: Active

**Architecture Decisions**: [ADR-0025](../../docs/adr/0025-adopt-multi-repo-backlog-harvester-active-use-hold-latch-and-artifact-burn-executor.md), [ADR-0015](../../docs/adr/0015-adopt-preemptible-host-governor-and-sticky-model-epoch-queue.md)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Stage Multi-Hour Backlog Without Starting While Using Machine (Priority: P1)

As the workstation owner actively working at the keyboard, I want to compile and stage 2-3 hours of actionable tasks from specs, issues, and checklists across my personal repositories (`alos`, `nectR`, `first-ade`, `vindicta-specs`) and engage a hold gate so nothing loads into GPU memory until I stop using the machine or explicitly resume.

**Why this priority**: Prevents desktop/VRAM disruption during active coding while eliminating manual per-job enqueueing.

**Independent Test**: Run backlog staging with an active-use hold gate; verify jobs populate the queue in `queued` state, ticking while active yields `held` or `held_user_active` with zero model loads, and idle expiry or `resume` opens execution.

**Acceptance Scenarios**:

1. **Given** an active workstation session, **When** `backlog stage` runs across the configured personal repositories, **Then** 2-3 hours of deduplicated tasks are inserted into the queue and a hold latch prevents execution while active.
2. **Given** an `idle_gate` hold latch requiring 300s of user inactivity, **When** the queue loop polls at 25s idle and then at 320s idle, **Then** the first poll returns `held_user_active` without loading weights and the second poll clears the latch and executes the top epoch job.

---

### User Story 2 - Resilient Queue Burn Producing Reviewable Deliverables & Optional Worktree Drafts (Priority: P2)

As the maintainer reviewing overnight local compute output, I want queued tasks to step down cleanly to installed fallback models when primary tags are missing, write structured Markdown deliverables (`results/<repo>/<job_id>.md` and `burn_digest.md`), optionally stage isolated local git worktree draft branches, and let me review/clear `review_pending` jobs.

**Why this priority**: Resolves silent HTTP 404 failures, 512-token truncations, SQLite-only outputs, and permanent 3-PR merge-cap deadlocks.

**Independent Test**: Execute queued `spec_audit`, `issue_plan`, and `task_patch` jobs where primary tier tags return 404; verify fallback model execution, Markdown artifact creation, optional `git worktree` branch creation, and `review` state transitions.

**Acceptance Scenarios**:

1. **Given** a `reasoner` job when `gemma4:12b` returns HTTP 404 and `qwen2.5-coder:7b-instruct` is installed, **When** the loop executes the job, **Then** the spinner steps down to the installed fallback model and writes `results/<repo>/<job_id>.md` plus a `burn_digest.md` entry.
2. **Given** 3 completed merge-flagged jobs in `review_pending`, **When** the operator runs `review --approve-all --repo alos`, **Then** those jobs transition to `succeeded` and subsequent merge jobs become runnable.

---

### Edge Cases

- Re-running `backlog stage` when jobs already exist skips existing `job_id` entries idempotently without failing on duplicate keys.
- Automated bot noise (`main-guard` warnings, telemetry dashboards) and superseded PR branches are excluded during harvesting.
- High background desktop VRAM can be bypassed explicitly for manual smoke burns via `--force` or configured via `ALOS_FOREIGN_VRAM_LIMIT_MB`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-3701**: System MUST provide a `QueueHoldLatch` (`run/queue_hold.json`) supporting `manual` (`pause`/`resume`) and `idle_gate` (`min_idle_s`) modes checked before model spin-up or job leasing.
- **FR-3702**: System MUST expose `pause` and `resume` CLI commands and `--hold` / `--arm-after-idle` staging flags so staged backlogs never start while the operator is actively using the machine.
- **FR-3703**: `ModelSpinner` MUST step down to installed `fallback_models` when a primary tier model tag is missing (`HTTP 404` / not found) and honor bridge hosts when local `ollama` binary is absent.
- **FR-3704**: System MUST support `--force` on `tick` and `burn` CLI runs plus `ALOS_FOREIGN_VRAM_LIMIT_MB` environment configuration so operators can run verified smoke burns despite elevated desktop VRAM.
- **FR-3705**: System MUST execute structured workflow types (`spec_audit`, `issue_plan`, `task_patch`, `test_draft`, `review_fix`) writing Markdown deliverables to `ALOS_HOME/results/<repo>/<job_id>.md` and appending `ALOS_HOME/results/burn_digest.md`.
- **FR-3706**: System MUST support optional isolated git worktree draft branch creation (`alos-burn/<job_id>`) when `create_worktree_branch` and a valid local checkout path are supplied.
- **FR-3707**: System MUST expose a `review` CLI command transitioning `review_pending` jobs to `succeeded`, `queued`, or `escalated` so per-repo merge caps never deadlock permanently.
- **FR-3708**: System MUST provide a `MultiRepoBacklogBuilder` (`backlog build`, `backlog stage`, `backlog summary`) harvesting SpecKit/OpenSpec unchecked tasks, actionable GitHub issues, and failing PRs across `alos`, `nectR`, `first-ade`, and `vindicta-specs` while filtering bot spam and duplicates.
- **FR-3709**: System MUST bundle a curated multi-repository backlog snapshot (`alos/templates/backlog/personal_repos_backlog.json`) targeting 2-3 hours of sticky-epoch execution for instant offline staging.

### Key Entities

- **BacklogItem**: Normalized cross-repository task (`job_id`, `repo_slug`, `workflow_type`, `model_tier`, `priority`, `estimated_minutes`, `source_ref`, `payload`).
- **QueueHoldState**: Persistent hold configuration (`mode`, `min_idle_s`, `reason`, `created_at`).
- **BurnDeliverable**: Structured Markdown artifact (`results/<repo>/<job_id>.md`) and optional worktree branch metadata.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Operators can stage 2-3 hours (120-180 estimated minutes) of cross-repository tasks in under 2 seconds from the bundled snapshot with 0 MB GPU memory allocated while active.
- **SC-002**: 100% of staged tasks remain unleased while `QueueHoldLatch` is active and automatically arm once user idle duration meets or exceeds `min_idle_s`.
- **SC-003**: 100% of completed non-prompt burn tasks emit a readable Markdown deliverable on disk and update the burn digest without manual SQLite queries.

## Assumptions

- `gh` CLI authentication is used when `--live-gh` refresh is requested; offline staging uses the package-bundled snapshot.
- Local git worktree draft branches never push or open remote pull requests without explicit human review.
