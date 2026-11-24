# Feature Specification: Preemptible Compute Governor & Sticky Epoch Queue

**Feature Branch**: `feat/preemptible-compute-governor`
**Created**: 2026-11-23
**Status**: Active (Slices 1 & 2 Implemented; Slice 4 Gateway Tracked in ADR-0016)
**Architecture Decisions**: [ADR-0015](../../docs/adr/0015-adopt-preemptible-host-governor-and-sticky-model-epoch-queue.md), [ADR-0016](../../docs/adr/0016-evaluate-local-model-gateway-routing-shim-vs-litellm-proxy.md)

---

## Intent

Turn an idle single-GPU Windows gaming workstation (NVIDIA RTX 5080 16 GB VRAM, i9-14900KF, 64 GB RAM) into a self-starting, preemption-safe local compute engine without burning cloud API budgets or interfering with gaming, desktop responsiveness, or thermal headroom.

The goal is **not** running loops to pin the GPU, but **reliable activation paired with provable sub-2-second yield**:
1. When the machine is idle and cool, the queue pulls work grouped by `model_tier` so weights stay hot in VRAM without PCIe swap thrashing.
2. When Direct3D fullscreen gaming starts, foreign VRAM spikes, or GPU/VRAM/CPU temperatures cross hysteresis thresholds, in-flight work checkpoints cleanly, active containers pause, and 100% of managed Ollama VRAM is reclaimed within `< 2.0s`.

---

## Functional Requirements

- **FR-001 (In-Process Telemetry Protocol)**: The system MUST define a `SensorProvider` protocol returning `TelemetrySnapshot` (`gpu_temp_c`, `vram_temp_c`, `cpu_temp_c`, `gpu_util_pct`, `total_vram_mb`, `used_vram_mb`, `managed_vram_mb`, `d3d_fullscreen`, `user_idle_seconds`, `blocked_process`), backed on Windows by zero-subprocess `ctypes` calls (`nvml.dll`, `shell32.SHQueryUserNotificationState`, `user32.GetLastInputInfo`).
- **FR-002 (Schmitt-Trigger Hysteresis State Machine)**: `HostGovernor` MUST transition deterministically across `ARMED_IDLE`, `WARM_ACTIVE`, `WARM_LINGER`, `THROTTLED`, `COOLING_CUTOFF`, and `USER_PREEMPTED` using separate trip and recovery thresholds plus cooldown dwell durations to prevent thermal/activity oscillation.
- **FR-003 (Sub-2-Second Preemption & Orphan Tree Eviction)**: Entering `COOLING_CUTOFF` or `USER_PREEMPTED` MUST signal active workers via cancellation event, pause registered Docker devcontainers (`docker pause`), request `keep_alive=0` model unload on the managed Ollama server, and terminate the entire Windows server process tree (`taskkill /PID /T /F`) if managed VRAM remains above threshold.
- **FR-004 (Managed Model Epoch Spinner)**: `ModelSpinner` MUST launch ephemeral Ollama instances per `model_tier` (`fast_coder`, `reasoner`, `architect`, `embed`) with tier-specific `OLLAMA_NUM_PARALLEL`, `OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`, and `OLLAMA_MAX_LOADED_MODELS=1`.
- **FR-005 (Warm Linger Keep-Alive)**: When the queue empties while the gate remains open and cool, `HostGovernor` MUST enter `WARM_LINGER` for a configurable window (default `600s`) so arriving jobs execute with 0ms cold-load delay, then evict VRAM upon linger expiry.
- **FR-006 (Sticky Model-Epoch Queue Leasing)**: `StickyEpochQueue` MUST persist jobs in `alos.db` (`PostgreSQL` `FOR UPDATE SKIP LOCKED` with `SQLite` transactional fallback), boosting effective priority for jobs matching `active_tier` up to a maximum epoch duration (`max_epoch_s`) to eliminate single-GPU weight-swap thrashing while preventing starvation.
- **FR-007 (Resumable Preemption Handoff)**: Preempted leases MUST transition to `preempted` while preserving `checkpoint_ns` (LangGraph `thread_id`) and NOT incrementing failure retry counts, allowing seamless resumption when the gate reopens.
- **FR-008 (Merge-Work PR Cap)**: When a `repo_slug` already has `>= max_open_merge_jobs` (default `3`) unreviewed merge-producing jobs, `StickyEpochQueue` MUST skip `requires_merge=True` jobs for that repository while continuing to lease `requires_merge=False` jobs.
- **FR-009 (Capacity & Thermal Ledger)**: The loop MUST append periodic ledger records capturing governor state, GPU/VRAM temperatures, VRAM usage, completed/waiting/preempted/overflow counts, and oldest job wait seconds.
- **FR-010 (Fault-Injected Spin-Down Verification)**: Automated tests (`T1` Game Launch Eviction, `T2` Orphaned Runner Tree Kill, `T3` Thermal Ramp Hysteresis) MUST verify spin-down behavior deterministically via synthetic `SensorProvider` stimuli, including against a live local Ollama server when available.

---

## Acceptance Scenarios

```gherkin
Feature: Preemptible Host Governor and Sticky Epoch Queue

  Scenario: T1 - Game launch preempts active model and evicts VRAM under 2 seconds
    Given a warm model tier "fast_coder" is active on the managed Ollama server
    When telemetry reports Direct3D fullscreen gaming or foreign VRAM above threshold
    Then the governor transitions immediately to "USER_PREEMPTED"
    And registered devcontainer workers are paused
    And managed Ollama VRAM drops to zero within 2.0 seconds

  Scenario: T2 - Hung Ollama runner is tree-killed on Windows spin-down
    Given a managed Ollama server process whose graceful unload fails or hangs
    When the governor executes spin-down eviction
    Then the server process tree is forcibly terminated
    And zero child runner processes remain holding GPU memory

  Scenario: T3 - Thermal ramp enforces Schmitt-trigger hysteresis without thrashing
    Given the governor is in "WARM_ACTIVE"
    When GPU core temperature rises to 76C then 83C
    Then the governor transitions to "THROTTLED" and then "COOLING_CUTOFF"
    When GPU core temperature cools slightly to 78C
    Then the governor remains in "COOLING_CUTOFF" without reloading any model
    When GPU core temperature holds at or below 58C for the recovery dwell window
    Then the governor returns to "ARMED_IDLE"

  Scenario: Sticky epoch leasing prevents model ping-pong
    Given queued jobs alternating between "fast_coder" and "reasoner" tiers
    And "reasoner" is currently hot in VRAM within its epoch window
    When the worker pulls consecutive jobs from the queue
    Then all "reasoner" jobs are leased before switching to "fast_coder"

  Scenario: Preempted job preserves checkpoint without consuming failure retries
    Given a leased job at attempt 1 with checkpoint namespace "lg-thread-42"
    When the job is preempted by user activity
    Then its state becomes "preempted" with attempts unchanged and checkpoint "lg-thread-42" preserved
    And it is leased first when the gate reopens
```
