# Technical Execution Plan: Preemptible Compute Governor & Sticky Epoch Queue

**Spec**: [`specs/031-preemptible-compute-governor/spec.md`](spec.md)
**ADRs**: [ADR-0014](../../docs/adr/0014-adopt-preemptible-host-governor-and-sticky-model-epoch-queue.md), [ADR-0015](../../docs/adr/0015-evaluate-local-model-gateway-routing-shim-vs-litellm-proxy.md)

---

## 1. Component Architecture

| Module | Responsibility | Key Classes & Functions |
| :--- | :--- | :--- |
| `alos/swarm/sensors.py` | Zero-subprocess Windows hardware/activity telemetry + deterministic fault-injection doubles. | `TelemetrySnapshot`, `SensorProvider`, `WindowsNativeSensor`, `ScriptedSensor` |
| `alos/swarm/governor.py` | Schmitt-trigger hysteresis FSM, `ModelSpinner` (`:11435` with `q8_0` KV cache & flash attention), `< 2.0s` VRAM eviction + tree kill, `docker pause`/`unpause` controller, CLI loop. | `GovernorState`, `HysteresisConfig`, `ModelTierSpec`, `ModelSpinner`, `ContainerPauser`, `HostGovernor` |
| `alos/db/models.py` & `alembic/versions/0002_*.py` | Persistent relational schema for `compute_work_queue` and `compute_capacity_ledger` across PostgreSQL 16 and SQLite. | `ComputeQueueJobModel`, `ComputeCapacityLedgerModel` |
| `alos/swarm/queue.py` | Pull-based ACID lease broker (`FOR UPDATE SKIP LOCKED` on Postgres, transactional fallback on SQLite) with sticky `model_tier` affinity, `requires_merge` PR cap, expired lease reclamation, and resumable `checkpoint_ns` preemption handoff. | `QueueConfig`, `LeasedJob`, `StickyEpochQueue` |

---

## 2. State Machine Thresholds (RTX 5080 + i9-14900KF Defaults)

- **Usage Preemption (`USER_PREEMPTED`)**:
  - Trip immediately (`0ms` debounce) when `d3d_fullscreen == True`, `blocked_process != None`, or `foreign_vram_mb > 3072`.
  - Recover to `ARMED_IDLE` only when `d3d_fullscreen == False`, `blocked_process == None`, `foreign_vram_mb <= 2200`, and `user_idle_seconds >= 300` (configurable).
- **Thermal Cutoff (`COOLING_CUTOFF`)**:
  - Trip immediately when `gpu_temp_c >= 82`, `vram_temp_c >= 94`, or `cpu_temp_c >= 92`.
  - Recover to `ARMED_IDLE` only when `gpu_temp_c <= 58`, `vram_temp_c <= 76`, and `cpu_temp_c <= 60` continuously for `recovery_dwell_s = 180`.
- **Thermal / Light-Use Throttle (`THROTTLED`)**:
  - Trip when `gpu_temp_c >= 75`, `vram_temp_c >= 88`, `cpu_temp_c >= 85`, or `user_idle_seconds < 60` (desk coding without game/VRAM pressure).
  - Recover to `WARM_ACTIVE` when `gpu_temp_c <= 65` and `cpu_temp_c <= 72` for `throttle_dwell_s = 120`.
- **Warm Linger (`WARM_LINGER`)**:
  - Entered from `WARM_ACTIVE` when queue yields `None` while gate is open; holds loaded tier warm for `warm_linger_s = 600` before unloading VRAM and returning to `ARMED_IDLE`.

---

## 3. Code Quality & Complexity Constraints

- Every function in `alos/swarm/*.py` MUST maintain Cyclomatic Complexity `CC <= 12` (verified by `tests/meta/test_code_quality_ast.py`).
- Zero bare `# noqa` or `# type: ignore` comments; strict `mypy` and `bandit` compliance.
- Full Alembic `upgrade head` and `downgrade base` round-trip compatibility.
