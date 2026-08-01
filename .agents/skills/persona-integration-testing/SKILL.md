---
name: persona-integration-testing
description: Automated skill for executing persona integration tests, verifying pre-push quality gates, and validating self-correction loops against BDD scenarios.
---

# Persona Integration Testing Skill

This skill governs testing executive persona behaviors (e.g. Alex in `specs/personas/alex_persona.md`), pre-push quality gate validation, and BDD scenario execution.

## Verification Workflow

1. **Execute All BDD & Persona Integration Tests**:
   ```bash
   uv run pytest tests/test_alex_persona_integration.py tests/test_sdd_bdd_features.py -v
   ```

2. **Verify Pre-Push Quality Gates**:
   - `uv run ruff check alos tests`
   - `uv run mypy alos tests`
   - `uv run bandit -r alos -s B101`
   - `uv run pyadr check-adr-repo --no-ansi`

3. **Gherkin Scenarios**:
   - All acceptance features live in `tests/features/` (01 through 09).
