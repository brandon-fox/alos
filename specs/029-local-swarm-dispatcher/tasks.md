# Implementation Tasks: Local Swarm Dispatcher

## Stage 1: one run

- [x] **Task 1**: Draft `spec.md` and `plan.md`
- [x] **Task 2**: Measure concurrent slots per model on a stock and a dispatcher-owned Ollama server
- [x] **Task 3**: Implement `alos/swarm/dispatcher.py` (phases, budgets, schema gate, resume, early abort, contention gate, ledger line)
- [x] **Task 4**: First real run: index 47 feature specifications on three models; record results in `docs/swarm.md`
- [x] **Task 5**: Fix the orphaned runner found by that run (kill the server's process tree)
- [x] **Task 6**: Unit tests in `tests/test_swarm_dispatcher.py` with a fake model client
- [x] **Task 7**: `scripts/swarm/bench_slots.py` to reproduce the slot measurements
- [ ] **Task 8**: Golden sets for the `classify` and `tag` classes (quality floor per class)
- [ ] **Task 9**: Confirm a detached run outlives the session that started it
- [ ] **Task 10**: Embeddings class (different endpoint)

## Stage 2: standing loop

- [ ] **Task 11**: Queue format and the standing loop
- [ ] **Task 12**: Hourly capacity ledger
- [ ] **Task 13**: Merge cap for work that opens pull requests
- [ ] **Task 14**: First-ADE compliance check as the acceptance gate for code changes
- [ ] **Task 15**: Cloud overflow lane, once one is shown to run headless

## Stage 3: feeders and the vault bus

- [x] **Task 16**: Draft the stage 3 section of `spec.md`
- [x] **Task 17**: Show a cloud lane runs headless (Antigravity CLI print mode)
- [x] **Task 18**: Prototype the five feeders, the bus collector and the nightly loop outside the repository
- [x] **Task 19**: Score the `prose` class on the eval-facts set
- [ ] **Task 20**: Run the test drafts from the 2026-11-09 night in the spec 030 sandbox before any new drafts are generated
- [ ] **Task 21**: Move the feeders into `alos/swarm/` with unit tests, after a week of nights
