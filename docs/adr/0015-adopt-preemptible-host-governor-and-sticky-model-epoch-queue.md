# Adopt Preemptible Host Governor and Sticky Model-Epoch Queue

* Status: accepted
* Deciders: Brandon Fox
* Date: 2026-11-23

Technical Story: `specs/032-preemptible-compute-governor/spec.md`

## Context and Problem Statement

ALOS runs on a single-GPU Windows workstation (NVIDIA RTX 5080 with 16 GB VRAM, Intel i9-14900KF, 64 GB RAM) that sits idle roughly 90% of the time while cloud LLM APIs (Claude, Gemini) incur token costs and strict rate quotas. Stage 1 (`specs/029-local-swarm-dispatcher/spec.md`) proved parallel-slot Ollama execution on an ephemeral server port, but only checked GPU contention once before starting a batch and operated without a persistent pull queue. How do we continuously pull work to keep local models hot during idle windows while guaranteeing immediate (`< 2.0s`), thrash-free spin-down whenever thermals rise or human/gaming activity resumes?

## Decision Drivers

* Sub-2-second VRAM eviction and container pause when Direct3D fullscreen gaming, foreign VRAM allocation, or active user load appears.
* Anti-thrashing thermal protection via Schmitt-trigger hysteresis across GPU core, GDDR7 memory, and CPU thermals.
* Zero-subprocess telemetry polling on Windows (`nvml.dll` + Win32 `user32`/`shell32` via `ctypes`) so idle monitoring does not prevent CPU C-states.
* Elimination of single-GPU weight-swap thrashing across `7B`, `12B`, and `30B` models via sticky `model_tier` epoch batching and `q8_0` KV-cache compression.
* Testability of spin-down behavior via deterministic synthetic fault injection against the live Ollama runtime without manual game launches.

## Considered Options

* Option 1: Windows-native `HostGovernor` + `ModelSpinner` paired with a SQLAlchemy/PostgreSQL (`SKIP LOCKED` + SQLite fallback) sticky `model_tier` epoch queue
* Option 2: Stateless cron polling invoking Stage 1 `dispatcher.py` over flat filesystem manifests with FIFO ordering
* Option 3: Dockerized GPU Ollama container managed purely via Docker Compose healthchecks and Redis FIFO queues

## Decision Outcome

Chosen option: "Option 1: Windows-native `HostGovernor` + `ModelSpinner` paired with a SQLAlchemy/PostgreSQL (`SKIP LOCKED` + SQLite fallback) sticky `model_tier` epoch queue", because native host access provides sub-millisecond NVML/Win32 D3D preemption signals and reliable Windows process-tree termination (`taskkill /T /F`), while sticky `model_tier` queue epochs keep weights hot in 16 GB VRAM without swap thrashing.

### Positive Consequences

* Reclaims 100% of managed Ollama VRAM within `< 2.0s` upon gaming or thermal cutoff, verified against orphaned `ollama_llama_server.exe` child processes.
* Groups queued jobs by `model_tier` with a `WARM_LINGER` keep-alive window so back-to-back tasks hit already-loaded weights at 0ms cold-load cost.
* Shares the existing `alos.db` PostgreSQL/SQLite persistence layer (`DatabaseManager`) for both job leases (`checkpoint_ns` resumability) and hourly capacity/thermal ledger records.

### Negative Consequences

* Splits execution across native Windows (sensors + Ollama runner) and WSL2 Docker (Postgres + devcontainers/sandboxes), requiring explicit port and `.wslconfig` coordination.
* Requires maintaining a `SensorProvider` abstraction so Linux CI runners validate state transitions deterministically without Windows DLLs.

## Pros and Cons of the Options

### Option 1: Windows-native `HostGovernor` + `ModelSpinner` paired with a SQLAlchemy/PostgreSQL (`SKIP LOCKED` + SQLite fallback) sticky `model_tier` epoch queue

* Good, because `nvml.dll`, `SHQueryUserNotificationState`, and `GetLastInputInfo` run in-process in `< 0.1ms` without spawning console subprocesses.
* Good, because sticky `model_tier` priority bonuses eliminate alternating `7B <-> 12B <-> 30B` PCIe weight thrashing on a 16 GB GPU.
* Good, because `DatabaseManager` runs identically against PostgreSQL (`FOR UPDATE SKIP LOCKED`) in production and SQLite in zero-container local boots or CI.
* Bad, because native Win32/NVML `ctypes` bindings require clean mockable fallbacks on non-Windows test hosts.

### Option 2: Stateless cron polling invoking Stage 1 `dispatcher.py` over flat filesystem manifests with FIFO ordering

* Good, because it adds zero database tables.
* Bad, because pre-run contention checks cannot preempt a 15-minute phase mid-flight when a game starts or GPU temperatures cross 82C.
* Bad, because FIFO manifest execution unloads and reloads multi-gigabyte models constantly or lets weights go cold between runs.

### Option 3: Dockerized GPU Ollama container managed purely via Docker Compose healthchecks and Redis FIFO queues

* Good, because all components live inside `docker-compose.yml`.
* Bad, because WSL2 `vmmemWSL` retains host RAM aggressively after container unloads, starving Windows games on the same machine.
* Bad, because Linux containers inside WSL2 cannot query Windows `SHQueryUserNotificationState` (D3D fullscreen game state) or `GetLastInputInfo` (HID idle time).

## Links

* Refines [ADR-0007](0007-adopt-sqlalchemy-orm-and-alembic-for-postgresql-data-models-and-migrations.md)
* Refines [ADR-0010](0010-adopt-langgraph-for-autonomous-self-reflection-loops-over-n8n-workflows.md)
