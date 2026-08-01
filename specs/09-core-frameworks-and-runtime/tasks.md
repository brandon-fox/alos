# Task Breakdown: Core Frameworks & Runtime Dependencies (Spec 09)

- [ ] Task 1: Refactor `alos/core/config.py` to use `pydantic-settings`.
- [ ] Task 2: Configure `structlog` in `alos/logs/` for structured JSON output.
- [ ] Task 3: Wrap external tool executions in `alos/integrations/mcp_gateway.py` with `tenacity` retry decorators.
- [ ] Task 4: Integrate `typer` and `rich` in `alos/cli.py` for rich CLI commands.
- [ ] Task 5: Add unit tests verifying setting validation and retry behavior.
