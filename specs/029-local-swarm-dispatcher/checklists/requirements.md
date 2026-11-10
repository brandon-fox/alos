# Requirements Traceability & Quality Gate Checklist

## Requirement Verification (stage 1)

Each line names the spec scenario and the test in `tests/test_swarm_dispatcher.py` that covers it.

- [x] **Phases by model**: `test_plan_phases_groups_by_model_in_roster_order`
- [x] **A manifest is wrong**: `test_plan_phases_refuses_bad_manifests`
- [x] **Output cap**: `test_judge_treats_a_capped_answer_as_failed_not_short`
- [x] **Wall clock**: `test_run_job_records_a_timeout_without_retrying`
- [x] **Schema gate**: `test_schema_errors_reports_the_first_violation`, `test_run_job_retries_once_with_the_validation_error_appended`, `test_run_job_escalates_after_the_retry_budget`
- [x] **Thinking is off by default**: `test_thinking_is_sent_as_false_only_when_the_model_supports_it`
- [x] **Resume**: `test_resume_skips_jobs_with_an_ok_result_and_finish_counts_them`
- [x] **Early abort**: `test_fan_out_aborts_when_the_first_ten_jobs_mostly_fail`
- [x] **The machine is in use**: `test_gate_reports_a_listed_process_and_foreign_gpu_memory`, `test_execute_reports_busy_before_anything_loads`
- [ ] **Parallel slots without a system setting**: exercised by hand (see `docs/swarm.md`); no automated test starts a real server
- [ ] **Ollama is not serving**: no automated test yet
- [ ] **Workers are offline and isolated**: holds by construction (a request carries one prompt and one input file); no automated test

## Not yet verified

- [ ] Stage 2 scenarios (standing loop, capacity ledger, merge cap, acceptance gate, overflow lane): specified, not built
- [ ] Quality floor for the `classify` and `tag` classes

## Quality Gates

- [x] Pytest passes: `pytest tests/test_swarm_dispatcher.py`
- [x] Ruff lint and format checks pass: `uv run ruff check alos tests scripts`
- [x] Mypy type checks pass: `uv run mypy alos`
- [x] Bandit passes: `uv run bandit -r alos -s B101`
