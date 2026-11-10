# Requirements Traceability & Quality Gate Checklist

## Requirement Verification

Each line names the spec scenario and the test in `tests/test_swarm_sandbox.py` that covers it.
Tests marked (container) start a real container and run in the `sandbox-isolation` CI job.

- [x] **A draft cannot change the repository**: `test_a_hostile_draft_is_blocked_on_every_route`, `test_a_destructive_draft_leaves_the_repository_untouched` (container)
- [x] **A draft cannot reach the network**: `test_a_hostile_draft_is_blocked_on_every_route` (container)
- [x] **A draft has nowhere to persist anything**: `test_a_hostile_draft_is_blocked_on_every_route` (container), `test_container_argv_carries_every_isolation_rule`
- [x] **A draft runs without privilege**: `test_a_hostile_draft_is_blocked_on_every_route` (container), `test_container_argv_carries_every_isolation_rule`
- [x] **The draft is the only thing collected**: `test_container_argv_carries_every_isolation_rule`, `test_a_sound_draft_passes_and_a_wrong_one_fails` (container)
- [x] **A draft never finishes**: `test_run_container_kills_the_container_by_name_when_the_clock_runs_out`, `test_a_draft_that_never_finishes_is_stopped_and_removed` (container)
- [x] **The sandbox cannot run**: `test_a_runtime_failure_is_the_sandbox_failing_not_the_draft`, `test_a_missing_runtime_is_a_sandbox_error`, `test_main_reports_a_sandbox_failure_with_exit_code_2`
- [x] **A mutant is applied without touching the source**: `test_a_mutant_is_mounted_read_only_over_the_file_it_replaces`, `test_mutants_are_killed_or_survive_and_the_source_is_never_changed` (container)
- [x] **Promotion** and **A test that cannot fail**: `test_a_passing_draft_is_promoted_only_if_a_mutant_makes_it_fail`, `test_a_failing_draft_is_never_tried_against_mutants`, `test_a_plan_runs_end_to_end_and_writes_results` (container)
- [x] **A mutant from a model is not trusted**: `test_mutant_source_rejects_escapes_and_code_that_does_not_compile`, `test_mutate_refuses_a_line_that_is_absent_or_unchanged`

## Not yet verified

- [ ] Memory, CPU and process limits are passed as flags but no test exhausts them
- [ ] Docker Desktop on Windows (paths and mounts)
- [ ] A real night's drafts

## Quality Gates

- [x] Pytest passes: `pytest tests/test_swarm_sandbox.py` (24 unit tests; 7 container tests with `ALOS_SANDBOX_IMAGE` set)
- [x] Ruff lint and format checks pass: `uv run ruff check alos tests`
- [x] Mypy type checks pass: `uv run mypy alos`
