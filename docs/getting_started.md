# Getting Started with ALOS

Welcome to **ALOS (Local Autonomous Life Operating System)**. ALOS supports two portable production deployment modes—**Standalone Portable Install** (recommended on Windows gaming workstations for zero-overhead NVML & Direct3D hardware preemption) and **Container / Devcontainer Mode**—as well as source-checkout development.

---

## 1. Prerequisites & Local Model Roster

- **Python / Packaging**: `uv` (manages Python 3.12+, lockfiles, wheels, and isolated tool environments).
- **Local Model Runtime**: [Ollama](https://ollama.com) serving on `127.0.0.1:11434`.
- **Optional Container Runtime**: Docker Desktop (WSL2 on Windows) for PostgreSQL 16, Redis, n8n, isolated test sandboxes, or containerized daemon deployments.

Pull the local capability-tier models once:

```powershell
ollama pull qwen2.5-coder:7b-instruct   # fast_coder primary (4 slots, 8k ctx, q8_0 KV)
ollama pull qwen2.5-coder:1.5b          # compact commit-pressure fallback (<1 GB)
ollama pull qwen2.5-coder:0.5b          # emergency ultra-low-commit fallback (<400 MB)
ollama pull gemma4:12b                  # reasoner tier   (4 slots, 8k ctx, q8_0 KV)
ollama pull qwen3-coder:30b             # architect tier  (1 slot, 8k ctx, q8_0 KV)
ollama pull nomic-embed-text            # embed tier      (4 slots, 8k ctx)
```

> [!TIP]
> **Windows Gaming Workstation Guardrail**: Cap WSL2 in `%USERPROFILE%\.wslconfig` (`memory=24GB`, `processors=12`, `autoMemoryReclaim=gradual`) and keep at least `16–32 GB` of Windows Virtual Memory (`pagefile.sys`) when running Docker Desktop alongside `7B`/`12B` CUDA models (`nvcuda64.dll` reserves OS commit charge equal to GPU allocations; if commit headroom gets tight, ALOS automatically steps down along `7b -> 3b -> 1.5b -> 0.5b`).

---

## 2. Deployment Option A: Portable Standalone Install (Zero Containers Required)

Installs self-contained `alos`, `alos-governor`, `alos-dispatcher`, and `alos-sandbox` binaries that run from **any directory** using `~/.alos` (`ALOS_HOME`) and an embedded SQLite queue/ledger database:

```powershell
# One-command portable wheel build, isolated runtime venv (~/.alos/runtime), bootstrap, and doctor check
.\scripts\install-portable.ps1

# Or install globally onto PATH via uv tool:
.\scripts\install-portable.ps1 -UseUvTool

# Optional: register (or remove) a user logon Windows Scheduled Task for the background daemon
.\scripts\install-portable.ps1 -RegisterStartupTask
.\scripts\install-portable.ps1 -UnregisterStartupTask
```

Once installed, run ALOS from anywhere without needing the Git checkout:

```powershell
alos bootstrap          # Idempotently seeds ~/.alos/vault, queue DB, logs, and alos.env
alos doctor --json      # Verifies ALOS_HOME, DB, vault, NVML GPU, Ollama models, and Docker
alos status             # Prints live governor FSM state + GPU/VRAM/HID telemetry
alos daemon             # Starts standing warm-linger loop (PID-locked, SIGTERM-safe)
```

---

## 3. Deployment Option B: Production Containers & Devcontainers

### Full Docker Compose Stack (PostgreSQL 16 + Redis + n8n + ALOS Daemon)

```powershell
Copy-Item .env.example .env   # Configure POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, N8N_ENCRYPTION_KEY

# Start Postgres, Redis, n8n, and the non-root (UID 10001) alos-daemon container
docker compose --profile alos up -d --build

# Check container health (backed by `alos doctor --json` HEALTHCHECK)
docker compose ps
```

### Standalone Production Container

```powershell
docker build -f Dockerfile -t alos:local .
docker run --rm -v alos_data:/data --add-host=host.docker.internal:host-gateway alos:local bootstrap
docker run --rm -v alos_data:/data --add-host=host.docker.internal:host-gateway alos:local doctor --json
```

### Portable Devcontainer

Open the repository in VS Code / Antigravity Dev Containers (uses `.devcontainer/devcontainer.json` with `--cpus=6`, `--memory=8g`, `--no-new-privileges`, and `host.docker.internal` Ollama routing).

---

## 4. Day-to-Day Operations & Monitoring

```powershell
# Enqueue work onto a capability tier (fast_coder | reasoner | architect)
alos enqueue --id job-01 --repo alos --tier fast_coder --prompt "Audit error handling."

# Execute one bounded cycle (or let `alos daemon` pull automatically)
alos tick

# Inspect recent GPU thermal, VRAM, and queue wait-time ledger entries
alos ledger --limit 10

# Run Dual-Loop Planner + Safety Matrix Evaluator against your Obsidian vault
alos ask "Plan focus blocks for tomorrow morning"

# Run CrewAI or SpecKit lifecycle commands
alos crew run --name code_quality --goal "alos/swarm"
alos speckit lifecycle --action list
```

### Live Monitoring Signals
- **Daemon Liveness File**: `~/.alos/run/health.json` (or `/data/run/health.json` in Docker) records atomic `status`, `governor_state`, `active_tier`, `pid`, and `updated_at`.
- **Single-Instance Lock**: `~/.alos/run/governor.lock` prevents duplicate daemons and automatically reclaims stale dead-PID locks.
- **Managed Epoch Server**: `Invoke-RestMethod http://127.0.0.1:11435/api/ps` shows the currently hot model and `size_vram` footprint.

---

## 5. Development Setup & Validation Gates

```powershell
uv sync --extra dev
.\.specify\scripts\powershell\setup-dev-environment.ps1
.\.specify\scripts\powershell\setup-git-workflow.ps1

# Run all 8 pre-handback gates (uv.lock, Ruff, Mypy, Bandit, pyadr, Pytest >=85%, @mocked + @live Behave)
.\scripts\run-validation-suite.ps1
```
