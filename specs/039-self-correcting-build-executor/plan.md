# Implementation Plan: Self-Correcting Build Executor

**Branch**: `039-self-correcting-build-executor` | **Date**: 2026-11-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/039-self-correcting-build-executor/spec.md`.

## Summary

Turn a queued `build` item into a verified, squash-merged change with no standing human gate. Phase 1 ships in small PRs on the modules ALOS already has (queue daemon, burn executor plumbing, spec 030 sandbox, `gh`), so the loop runs before any framework work. Phase 2 moves orchestration onto LangGraph, CrewAI and n8n behind spec 036 ports, with the same baseline.

Order matters: the governor fix and the pure checks (risk, leak) land first because the executor depends on them; the publisher lands last because it is the only part that writes to GitHub.

## Technical Context

**Language/Version**: Python `>=3.11,<3.14` (MyPy 3.12)
**Primary Dependencies**: existing only in phase 1: `sqlalchemy`, `pydantic`, stdlib `subprocess`/`json`/`urllib`, `gh` CLI, Docker CLI (sandbox), `ade-compliance` (First-ADE). Phase 2: `langgraph`, `crewai` (already declared in `pyproject.toml`).
**Storage**: `ALOS_HOME/queue/compute_queue.db`, `ALOS_HOME/worktrees/<job_id>/attempt-<n>`, `ALOS_HOME/results/<repo>/<job_id>/attempt-<n>.md`, `ALOS_HOME/results/escalations.md`, risk config in `alos/templates/build/risk.json`
**Testing**: `pytest` (`>= 90%` branch coverage), `behave` `@mocked`, a fixture git repository with a known failing test for end-to-end runs, scripted fake model client
**Target Platform**: Windows 11 workstation (single GPU) + Linux sandbox containers
**Constraints**: every PR `< 1000` non-lockfile lines; `CC <= 12`; verified commits (First-ADE A7); PRs target `main` only (issue #180)
**Scale/Scope**: ALOS first; 20 `build` items for the kill-criteria read

## Constitution Check

- **I. Determinism & Verification**: PASS. Every mutation is Draft (diff) then Validate (FR-3904) before anything is pushed.
- **II. Local-First Privacy**: PASS. Models run on local Ollama tiers; the cloud lane is opt-in per item (`allow_cloud_overflow`).
- **III. Decision Provenance**: PASS. Each attempt writes a record with model, context sizes, diff and step results (FR-3914).
- **IV. Test-First Development**: AMEND. "User approved" is replaced by evidence (red-green and mutation steps) through ADR-0028 (FR-3915). Until that ADR merges, PR-6 and PR-7 ship behind a disabled flag.
- **V. Safety Matrix Enforcement**: AMEND. Code merges are classified LOW / HIGH / PROTECTED; only PROTECTED needs a human (FR-3908, FR-3915).
- **VI. Human-Centric Non-Intrusiveness**: PASS. Runs through the governor and hold latch; FR-3916 stops self-preemption.
- **VII. Code Quality**: PASS. `ruff`, `mypy`, `bandit`, coverage floor and mutation score apply to the executor's own code.

## Project Structure

```text
specs/039-self-correcting-build-executor/
  spec.md  plan.md  tasks.md  checklists/requirements.md

alos/
  swarm/
    governor.py      # FR-3916: grace window for managed loads
    build/
      __init__.py
      risk.py        # FR-3908 classifier (PROTECTED module)
      leak.py        # FR-3904 step 7 scanner
      baseline.py    # FR-3904/3905 steps, sandbox calls (PROTECTED module)
      context.py     # FR-3903 context assembly and trimming
      executor.py    # FR-3901/3906/3907 attempt loop, spec_refine, escalation
      publish.py     # FR-3909/3910/3912/3913 API commit, PR, merge cap, post-merge watch
  templates/
    build/risk.json  # path lists (PROTECTED)
tests/
  test_build_risk.py  test_build_leak.py  test_build_baseline.py
  test_build_executor.py  test_build_publish.py  test_governor_managed_load.py
  fixtures/build_repo/   # tiny repository with one known failing test
  features/self_correcting_build_executor.feature   # "# spec: 039-self-correcting-build-executor"
docs/adr/0028-*.md
```

## Phases and PRs

| PR | Scope | Requirements | Resolves |
| --- | --- | --- | --- |
| PR-1 | Spec, plan, tasks, checklist; spec 029 pointers | all (definition) | V3, V4, V8 |
| PR-2 | ADR-0028 and constitution IV/V amendment (PROTECTED: maintainer merges) | FR-3915 | |
| PR-3 | Governor managed-load grace window | FR-3916 | |
| PR-4 | Risk classifier, risk config, leak scanner | FR-3908, FR-3904.7 | |
| PR-5 | Worktrees and baseline runner in the sandbox | FR-3902, FR-3904, FR-3905, FR-3906 | V1, V6 |
| PR-6 | `build` workflow, context assembly, attempt loop, `spec_refine`, escalation list, attempt records | FR-3901, FR-3903, FR-3907, FR-3911, FR-3914 | V2, V5 |
| PR-7 | Publisher: API commit, PR, merge cap, post-merge watch, auto-hold and revert | FR-3909, FR-3910, FR-3912, FR-3913 | V7 |
| PR-8 | Dogfood: 5 LOW `build` items from open ALOS spec tasks; record results in `docs/swarm.md` | SC-001 to SC-006 | |
| PR-9+ | Phase 2 target state: LangGraph graph, CrewAI crews, n8n bridge and workflow | Target state | |

## Running as is (before PR-3 lands)

- The queue daemon runs as the logon task `ALOS-Preemptible-Governor`, draining spec 037 burn items into Markdown deliverables.
- `ALOS_FOREIGN_VRAM_LIMIT_MB=14500` is set for the workstation user so the governor does not preempt its own model loads (V8).
- The nightly prototype outside the repository is retired; the daemon replaces it.

## Known gaps

- Main Guardian has failed its last two runs; PR-7's post-merge watch needs a green baseline on `main` to compare against.
- The 17-PR draft stack (#161 to #177) is far behind `main`; the merge cap counts open loop PRs only, so it does not interfere, but the stack should be closed or rebuilt separately.
- `ade-compliance` engines are heuristics by their own README; the test frame carries most of the baseline's weight.
