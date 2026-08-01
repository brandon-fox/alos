# Getting Started with ALOS

Welcome to **ALOS (Local Autonomous Life Operating System)**! This guide will take you step-by-step through setting up your local development environment, initializing your local vault memory, running Docker services, executing the test suite, and interacting with the system.

---

## 1. Prerequisites & System Requirements

Before setting up ALOS, ensure your system meets the following requirements:

- **Operating System**: Windows 10/11, macOS, or Linux (Windows PowerShell 7+ recommended on Windows).
- **Python**: Python 3.10 or higher (Python 3.12 recommended).
- **Package & Environment Manager**: `uv` (modern, ultra-fast Python package installer).
- **Container Engine**: Docker Desktop or Podman (for running PostgreSQL + `pgvector` locally).
- **Git**: Git with SSH commit signing configured (`gpg.format=ssh`).

---

## 2. Quickstart Installation

Follow these steps to clone and bootstrap the repository:

### Step 1: Clone the Repository & Checkout Feature Branch
```powershell
git clone https://github.com/bfoxt/n8nSetup.git
cd n8nSetup
```

### Step 2: Install Dependencies with `uv`
ALOS uses `uv` for deterministic dependency resolution. Install all dependencies and development extras:

```powershell
# Sync core dependencies and development tools (pytest, ruff, mypy, bandit)
uv sync --extra dev
```

### Step 3: Run Automated Environment Setup Scripts
ALOS includes automated PowerShell scripts in `.specify/scripts/powershell/` to configure pre-commit hooks, directory structures, and git signing rules:

```powershell
# Initialize dev environment and virtualenv
.\.specify\scripts\powershell\setup-dev-environment.ps1

# Configure git workflow, pre-commit hooks, and signing
.\.specify\scripts\powershell\setup-git-workflow.ps1
```

---

## 3. Launching Local Infrastructure (PostgreSQL & Vector DB)

ALOS uses a local PostgreSQL database with `pgvector` for structured state storage and hybrid search:

```powershell
# Spin up PostgreSQL + pgvector container in the background
docker compose up -d
```

To verify that the database container is running properly:
```powershell
docker compose ps
```

---

## 4. Running the Quality & Test Suite

ALOS enforces **100% test passing** and zero-tolerance quality gates before any code can be committed or merged.

### Run All Unit & Integration Tests
```powershell
uv run pytest
```

### Run Static Type Checker (Mypy)
```powershell
uv run mypy alos tests
```

### Run Linter & Formatter (Ruff)
```powershell
uv run ruff check alos tests
```

### Run Security Audit (Bandit)
```powershell
uv run bandit -r alos
```

### Run All Pre-Push Quality Hooks
To test the exact pre-push quality gate that CI/CD and git hooks enforce:
```powershell
uv run pre-commit run --all-files --hook-stage pre-push
```

---

## 5. Directory Blueprint: Where Things Live

Once initialized, your project layout looks like this:

```
n8nSetup/
├── alos/                     # Core Python Package
│   ├── core/                 # Dual-Loop engine (Planner, Evaluator, Graph)
│   ├── db/                   # SQLAlchemy 2.0 ORM models & Alembic migrations
│   ├── memory/               # Local RAG, VectorStore, Obsidian Vault engine
│   ├── integrations/         # MCP gateways & n8n workflow client
│   └── schemas/              # Pydantic v2 action models & schemas
├── docs/                     # Human Documentation Suite & ADRs
│   ├── adr/                  # Architectural Decision Records (managed via pyadr)
│   ├── idea.md               # Core vision, safety matrix, & philosophy
│   ├── architecture.md       # Technical architecture & component deep-dive
│   ├── specs_setup.md        # SpecKit (SDD), BDD, and TDD workflow
│   └── getting_started.md    # This getting started guide
├── specs/                    # SpecKit Feature Specifications (specs/01- through 18-)
├── tests/                    # Unit, Integration, & BDD Gherkin test suites
├── vault/                    # Local Obsidian Markdown Brain (User Profile, Preferences)
│   ├── USER_PROFILE.md       # User identity, contacts, roles
│   ├── PREFERENCES.md        # Explicit user rules (e.g., meeting constraints)
│   └── CORRECTION_LEDGER.md  # Historical correction ledger
├── docker-compose.yml        # Local PostgreSQL + pgvector service
├── pyproject.toml            # Project dependencies, Ruff, Mypy, and Pytest configs
└── README.md                 # Project landing page
```

---

## 6. Using the ALOS CLI

ALOS exposes a command-line interface (`alos`) powered by `typer`:

```powershell
# Inspect system status and vault connectivity
uv run alos inspect

# Evaluate a sample action against the Safety Matrix and local preferences
uv run alos eval --action-type "google_calendar_create_event" --summary "Sync with Alex"

# Execute a reasoning graph run
uv run alos run --prompt "Plan focus time for tomorrow morning"
```

---

## 7. Troubleshooting & Frequently Asked Questions

> [!TIP]
> **Issue**: `ModuleNotFoundError: No module named 'alos'` when running pytest directly.
> **Fix**: Ensure you run pytest via `uv run pytest`, which automatically respects `pythonpath = ["."]` in `pyproject.toml`.

> [!WARNING]
> **Issue**: `pyadr` command fails or reports ADR inconsistencies.
> **Fix**: Never edit ADR files manually inside `docs/adr/`. Always use `uv run pyadr propose` or `uv run pyadr check-adr-repo`.

> [!NOTE]
> **Issue**: Git push fails due to unsigned commits.
> **Fix**: Ensure your SSH or GPG key is registered with Git (`git config gpg.format ssh` and `git config user.signingkey ~/.ssh/id_ed25519.pub`). All commits in ALOS must be signed.
