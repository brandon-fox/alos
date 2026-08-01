# Implementation Plan: Open-Source Core & Dual-Repo Architecture

## Technical Strategy
1. **Engine Configuration**: Update `ALOSConfig` in `alos/core/config.py` to add `workflows_dir: str` backed by `ALOS_WORKFLOWS_DIR`.
2. **Templates & Mock Setup**:
   - Seed `vault.example/` with default user profiles and preferences.
   - Seed `workflows.example/` with sample n8n workflow JSON schemas.
3. **Environment & Security**:
   - Create `.env.example` with comprehensive variable definitions and safe placeholders.
   - Create `LICENSE` with MIT License terms.
   - Create `docker-compose.override.yml.example` for volume mounting.
4. **Git Hygiene**:
   - Ignore `vault/` and `workflows/` working paths in `.gitignore`.
5. **CI/CD**:
   - Create `.github/workflows/ci.yml` running `pytest`, `ruff`, and `mypy` on push/PR to main.
