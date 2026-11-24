# Implementation Plan: Multi-Repo Backlog Harvester, Active-Use Hold Gate, and Verified Artifact Burn

**Branch**: `037-backlog-staging-and-burn` | **Date**: 2026-11-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/037-backlog-staging-and-burn/spec.md` and [ADR-0025](../../docs/adr/0025-adopt-multi-repo-backlog-harvester-active-use-hold-latch-and-artifact-burn-executor.md).

## Summary

Deliver end-to-end multi-repository backlog staging, active-desk hold gating, resilient model fallback, and artifact-producing queue burn across three incremental PRs (`<= 1000` LOC guard): (1) SpecKit 037 + `ADR-0025`, (2) `QueueHoldLatch` (`pause`/`resume`/`idle_gate`), `ModelSpinner` missing-tag fallback, `alos/swarm/burn.py` Markdown + optional `git worktree` executor, and `review`/`burn`/`--force` CLI commands, and (3) `alos/swarm/backlog.py` multi-repo GitHub/SpecKit/OpenSpec harvester plus a curated ~2.6-hour bundled backlog across `alos`, `nectR`, `first-ade`, and `vindicta-specs`.

## Technical Context

**Language/Version**: Python `>=3.11,<3.14` (MyPy 3.12; Ruff `py310`)
**Primary Dependencies**: `pydantic>=2.0`, `sqlalchemy>=2.0.52`, stdlib `subprocess`/`json`/`urllib` (`gh` CLI optional for `--live-gh`)
**Storage**: `ALOS_HOME/queue/compute_queue.db` (SQLite WAL / PostgreSQL), `ALOS_HOME/run/queue_hold.json`, `ALOS_HOME/results/<repo>/<job_id>.md`
**Testing**: `pytest` (`>= 90%` branch coverage), `behave` (`@mocked`), AST complexity `CC <= 12`, AST mutation kill rate `>= 85%`
**Target Platform**: Windows 11 RTX 5080 host + Linux containers/VMs
**Project Type**: Local-first autonomous CLI & preemptible single-GPU compute queue
**Performance Goals**: `< 1.0s` bundled backlog staging; `0 MiB` VRAM while hold latch is active; `< 2.0s` preemption eviction
**Constraints**: Every PR `< 1000` non-lockfile lines; `CC <= 12`; zero bare `# noqa` / `# type: ignore`; SSH-signed commits (`First-ADE A7`)
**Scale/Scope**: 4 personal repositories (`alos`, `nectR`, `first-ade`, `vindicta-specs`), ~45-55 curated tasks (~150-170 estimated GPU burn minutes)

## Constitution Check

- **I. Determinism & Verification**: PASS -- All burned outputs write reviewable drafts/worktrees locally (`Plan/Draft -> Validate`); zero unreviewed external writes.
- **II. Local-First Privacy**: PASS -- Execution runs strictly on local Ollama tiers (`fast_coder`, `reasoner`, `architect`, `embed`) and local filesystem.
- **III. Decision Provenance**: PASS -- Queue state transitions, ledger metrics, and burn digests persist deterministically with source references.
- **IV. Test-First Development**: PASS -- Failing unit and `@mocked` BDD scenarios authored before implementation in each slice.
- **V. Safety Matrix Enforcement**: PASS -- Local artifact writes (`MEDIUM`) are schema/structure bounded; external PR/push (`HIGH`) remains human-gated.
- **VI. Human-Centric Non-Intrusiveness**: PASS -- `QueueHoldLatch` guarantees staged backlogs never cold-load models while the user is actively using the machine.
- **VII. Code Quality & Fix-First**: PASS -- Enforces `ruff`, `mypy`, `bandit`, `CC <= 12`, `>= 90%` coverage, and `>= 85%` mutation score.

## Project Structure

### Documentation (this feature)

```text
specs/037-backlog-staging-and-burn/
├── spec.md
├── plan.md
├── tasks.md
└── checklists/
    └── requirements.md
```

### Source Code (repository root)

```text
alos/
├── cli.py                                         # Forward pause, resume, review, burn, backlog commands
├── runtime.py                                     # RuntimePaths.hold_file, results_dir, QueueHoldLatch, review_jobs
├── swarm/
│   ├── governor.py                                # HTTP 404 / uninstalled primary fallback + ALOS_FOREIGN_VRAM_LIMIT_MB
│   ├── queue.py                                   # Hold latch gate, --force, pause/resume/review/burn/backlog CLI wiring
│   ├── burn.py                                    # Structured Markdown deliverable + optional git worktree executor
│   └── backlog.py                                 # MultiRepoBacklogBuilder (live gh + SpecKit/OpenSpec + bundle stage)
└── templates/
    └── backlog/
        ├── __init__.py
        └── personal_repos_backlog.json            # Curated 2.6h multi-repo backlog across alos, nectR, first-ade, vindicta-specs

features/
└── backlog_hold_and_burn.feature                  # @mocked Behave scenarios for hold gate, burn artifacts, and backlog stage

tests/
├── test_backlog_hold_and_burn.py                  # Unit & integration tests for hold latch, fallback, burn, review, worktrees
└── test_multi_repo_backlog.py                     # Unit & integration tests for harvester, noise filter, idempotent staging
```

**Structure Decision**: Extends `alos/runtime.py` and `alos/swarm/` with cohesive, low-complexity (`CC <= 10`) modules `burn.py` and `backlog.py` plus package-bundled `alos/templates/backlog/` data so wheel installs remain 100% self-contained outside a git checkout.
