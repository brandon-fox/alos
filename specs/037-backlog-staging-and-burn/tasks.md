# Tasks: Multi-Repo Backlog Harvester, Active-Use Hold Gate, and Verified Artifact Burn

**Input**: `/specs/037-backlog-staging-and-burn/` (`spec.md`, `plan.md`, `checklists/requirements.md`) and `docs/adr/0025-*.md`

**Prerequisites**: `plan.md`, `spec.md`, `checklists/requirements.md`

## Phase 1: Governance & Specification (`PR-1`)

- [x] T001 Record and accept `ADR-0025` via `pyadr` CLI in `docs/adr/0025-adopt-multi-repo-backlog-harvester-active-use-hold-latch-and-artifact-burn-executor.md` and `docs/adr/index.md`
- [x] T002 Initialize `specs/037-backlog-staging-and-burn/{spec,plan,tasks}.md` and `checklists/requirements.md` via explicit SpecKit PowerShell scripts and update `docs/traceability.md`

## Phase 2: Hold-While-Active Gate, Resilient Model Fallback & Artifact Burn (`PR-2` — `[US1]` & `[US2]`)

**Goal**: Prevent cold-start disruption while using the workstation, step down cleanly when primary Ollama tier tags return 404, write structured Markdown deliverables + optional git worktree branches, and unlock `review_pending` merge caps.

- [x] T003 [P] [US1] Write failing unit and `@mocked` BDD scenarios for `QueueHoldLatch` (`manual` & `idle_gate`), `pause`/`resume`, `--force`, missing-tag fallback, artifact deliverables, git worktree drafts, and `review` transitions in `tests/test_backlog_hold_and_burn.py` and `features/backlog_hold_and_burn.feature`
- [x] T004 [US1] Implement `QueueHoldLatch` (`hold_file`, `results_dir`) and `review_jobs()` state helper in `alos/runtime.py`
- [x] T005 [US2] Implement HTTP 404 / uninstalled primary tier model step-down to installed `fallback_models`, remote bridge fallback, and `ALOS_FOREIGN_VRAM_LIMIT_MB` configuration in `alos/swarm/governor.py`
- [x] T006 [US2] Implement `alos/swarm/burn.py` (`artifact_burn_executor`) writing `ALOS_HOME/results/<repo>/<job_id>.md`, updating `burn_digest.md` + `vault/Bus/Results/`, and supporting optional `git worktree` branch `alos-burn/<job_id>` and sandbox test checks
- [x] T007 [US1] Wire `QueueHoldLatch`, `artifact_burn_executor`, `--force`, and CLI commands (`pause`, `resume`, `review`, `burn`) into `alos/swarm/queue.py` and `alos/cli.py`

## Phase 3: Multi-Repo GitHub Backlog Harvester & Curated 2.6h Bundle (`PR-3` — `[US1]`)

**Goal**: Harvest SpecKit/OpenSpec tasks, actionable GitHub issues, and failing PRs across `alos`, `nectR`, `first-ade`, and `vindicta-specs`, bundle a ~2.6-hour sticky-epoch snapshot, and expose `alos backlog {build,stage,summary}`.

- [x] T008 [P] [US1] Write failing unit and `@mocked` BDD scenarios for multi-repo SpecKit/OpenSpec/GitHub harvesting, bot-spam filtering, idempotent queue deduplication, and `backlog stage --hold` in `tests/test_multi_repo_backlog.py` and `features/backlog_hold_and_burn.feature`
- [x] T009 [US1] Author curated multi-repository backlog bundle (`alos/templates/backlog/personal_repos_backlog.json`) covering `brandon-fox/alos`, `brandon-fox/nectR`, `brandon-fox/first-ade`, and `brandon-fox/vindicta-specs` and register package-data in `pyproject.toml`
- [x] T010 [US1] Implement `alos/swarm/backlog.py` (`MultiRepoBacklogBuilder` for bundled + `--live-gh` harvesting, duration estimation, and idempotent hold-gated staging) and wire `alos backlog` CLI in `alos/swarm/queue.py` and `alos/cli.py`

## Phase 4: Verification, Traceability & Polish

- [x] T011 Regenerate `docs/traceability.md` via `scripts/traceability.py`, mark `tasks.md` complete, and verify full `ruff`, `mypy`, `bandit`, `pytest >= 90%`, `behave @mocked`, fuzz, and AST mutation gates
