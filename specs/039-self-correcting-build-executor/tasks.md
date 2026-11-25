# Tasks: Self-Correcting Build Executor

**Input**: `/specs/039-self-correcting-build-executor/` (`spec.md`, `plan.md`, `checklists/requirements.md`)

**Prerequisites**: `plan.md`, `spec.md`

Every implementation task starts with a failing test (`pytest` and, where a scenario exists, `behave @mocked`) and ends green with the repository's quality gates.

## Phase 1: Definition and governance (`PR-1`, `PR-2`)

- [x] T001 Write `spec.md`, `plan.md`, `tasks.md` and `checklists/requirements.md`; point spec 029 Tasks 13 and 14 at this spec
- [x] T002 Resolve V3 (API-created commits are verified and noreply-authored), V4 (branch prefixes) and V8 (governor self-preemption) by probe
- [ ] T003 Record ADR-0028 (evidence-gated autonomous build executor) and amend constitution principles IV and V per FR-3915; open as a PROTECTED PR for the maintainer to merge

## Phase 2: Foundations (`PR-3`, `PR-4`)

- [ ] T004 [P] [US1] Failing tests for a managed-load grace window: VRAM growth while the queue's own model loads is not foreign (FR-3916) in `tests/test_governor_managed_load.py`
- [ ] T005 [US1] Implement the grace window in `alos/swarm/governor.py`; once green, drop the raised `ALOS_FOREIGN_VRAM_LIMIT_MB` from the workstation
- [ ] T006 [P] [US3] Failing tests for the LOW / HIGH / PROTECTED classifier over fixture diffs, including that `risk.json` and the build modules classify as PROTECTED, in `tests/test_build_risk.py`
- [ ] T007 [US3] Implement `alos/swarm/build/risk.py` and `alos/templates/build/risk.json`
- [ ] T008 [P] [US1] Failing tests for the leak scanner (local paths, usernames, machine names, non-noreply emails) in `tests/test_build_leak.py`
- [ ] T009 [US1] Implement `alos/swarm/build/leak.py`

## Phase 3: Baseline in the sandbox (`PR-5`)

- [ ] T010 [US1] Resolve V1: run the full suite inside the sandbox `full` image with `--network none`, a read-only mount and a writable tmpfs for cache, coverage and basetemp; record the command in `docs/swarm.md`
- [ ] T011 [US1] Resolve V6: run `ade-compliance check-all` on a fixture with a known violation and record whether the exit code is non-zero
- [ ] T012 [P] [US1] [US2] Failing tests for worktree creation per attempt and each baseline step's pass, fail and flaky results against `tests/fixtures/build_repo/`, in `tests/test_build_baseline.py`
- [ ] T013 [US1] Implement `alos/swarm/build/baseline.py` (steps `apply` to `leak`, sandbox for `static` to `mutation`, trimmed feedback per FR-3906)

## Phase 4: Executor (`PR-6`)

- [ ] T014 [US2] Resolve V2: measure `qwen3-coder:30b` at 16k context beside the desktop; set the `architect` tier context and fallback in the roster
- [ ] T015 [US2] Resolve V5: run the headless cloud lane on one fixture item and record whether its diff applies
- [ ] T016 [P] [US1] [US2] Failing tests with a scripted model for context assembly, the attempt limit, cloud overflow, `spec_refine` then one more attempt, escalation entries and attempt records, in `tests/test_build_executor.py` and `tests/features/self_correcting_build_executor.feature`
- [ ] T017 [US1] [US2] Implement `alos/swarm/build/context.py` and `alos/swarm/build/executor.py`; register the `build` workflow type in the queue and the burn executor

## Phase 5: Publisher (`PR-7`)

- [ ] T018 [P] [US1] [US4] Failing tests with a fake GitHub client for API commit creation, branch naming, PR body, `do-not-merge` on PROTECTED, the merge cap, the post-merge watch, auto-hold, revert PR and hold auto-clear, in `tests/test_build_publish.py`
- [ ] T019 [US1] [US4] Implement `alos/swarm/build/publish.py` on `gh api` (`createCommitOnBranch`, PR create, check-run reads)
- [ ] T020 [US1] Resolve V7: one fixture PR created through the API squash-merges through Auto Merge after `ci-merge-gate`

## Phase 6: Dogfood and read-out (`PR-8`)

- [ ] T021 Stage 5 LOW `build` items from open ALOS spec tasks; run them unattended; record merged, escalated and attempt counts in `docs/swarm.md`
- [ ] T022 Regenerate `docs/traceability.md` and mark completed tasks

## Phase 7: Target state (`PR-9` onwards)

- [ ] T023 Move the attempt cycle onto a LangGraph state graph on the spec 014 pattern, behind a spec 036 port
- [ ] T024 Run `spec_refine` through the `speckit_architect` crew and the HIGH reviewer through the `code_quality` crew
- [ ] T025 Expose the queue over the spec 036 T023 HTTP bridge and build the n8n workflow that schedules runs, fans out across repositories and receives escalations and post-merge results
