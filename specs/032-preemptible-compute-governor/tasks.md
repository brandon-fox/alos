# Implementation Tasks: Preemptible Compute Governor & Sticky Epoch Queue

**Spec**: [`specs/032-preemptible-compute-governor/spec.md`](spec.md)

---

- [x] **Task 1**: Propose and accept `ADR-0015` (`HostGovernor` + `StickyEpochQueue`) and record `ADR-0016` (Proposed comparison of Governor `/v1/chat/completions` shim vs. LiteLLM Proxy) via `pyadr`.
- [x] **Task 2**: Implement `alos/swarm/sensors.py` with `TelemetrySnapshot`, `SensorProvider` protocol, zero-subprocess `WindowsNativeSensor` (`nvml.dll`, `SHQueryUserNotificationState`, `GetLastInputInfo`), and `ScriptedSensor` fault-injection provider.
- [x] **Task 3**: Implement `alos/swarm/governor.py` with Schmitt-trigger `HostGovernor` FSM, `ModelSpinner` (`OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`), `< 2.0s` VRAM eviction + Windows process-tree kill, and `ContainerPauser`.
- [x] **Task 4**: Add `ComputeQueueJobModel` and `ComputeCapacityLedgerModel` to `alos/db/models.py` plus reversible Alembic migration `0002_add_compute_queue_and_ledger.py`.
- [x] **Task 5**: Implement `alos/swarm/queue.py` (`StickyEpochQueue`) with sticky `model_tier` epoch scoring, `FOR UPDATE SKIP LOCKED`, `requires_merge` PR cap, expired lease recovery, resumable `checkpoint_ns` preemption release, and capacity ledger recording.
- [x] **Task 6**: Author BDD feature `tests/features/preemptible_compute_governor.feature` and unit/integration/live-GPU tests (`tests/test_swarm_governor.py`, `tests/test_swarm_queue.py`) covering `T1–T3` spin-down, hysteresis anti-thrash, sticky epochs, and live RTX 5080 eviction.
- [x] **Task 7**: Author full `behave` BDD suites (`features/governor_spindown.feature`, `features/sticky_epoch_queue.feature`, `features/cli_and_live_integration.feature`) running both `@mocked` and `@live` RTX 5080 + Ollama integration scenarios, wire `pytest-light-unit` into `pre-commit`, and add `scripts/run-validation-suite.ps1`.
- [x] **Task 8**: Verify `ruff`, `mypy`, `bandit`, `pyadr check-adr-repo`, AST complexity gate (`CC <= 12`), full `pytest` coverage, and full `@mocked` + `@live` `behave` runs.
