# Quality Gate Checklist: Preemptible Compute Governor (031)

- [x] `spec.md`, `plan.md`, `tasks.md`, and `checklists/requirements.md` present under `specs/031-preemptible-compute-governor/`.
- [x] `ADR-0014` (Accepted) and `ADR-0015` (Proposed gateway evaluation) verified by `uv run pyadr check-adr-repo --no-ansi`.
- [x] `T1` (Game launch `< 2.0s` VRAM eviction), `T2` (Orphaned runner process-tree kill), and `T3` (Schmitt-trigger thermal hysteresis without bounce) verified in automated tests and against live RTX 5080 hardware.
- [x] Sticky `model_tier` queue leasing, `WARM_LINGER` keep-alive, `requires_merge` PR cap, and `checkpoint_ns` preemption resume verified.
- [x] Alembic migration `0002` passes `upgrade head` and `downgrade base` cleanly.
- [x] All functions across `alos/` satisfy Cyclomatic Complexity `CC <= 12`.
- [x] `pre-commit` executes fast light unit tests on every commit, and `scripts/run-validation-suite.ps1` passes full `pytest` (`>= 85%` coverage) plus `@mocked` and `@live` `behave` BDD suites.
- [x] Zero Ruff, Mypy, or Bandit findings.
