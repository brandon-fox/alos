# Architecture Plan: Core Frameworks & Runtime Dependencies (Spec 09)

## Architecture & Component Mapping

```mermaid
graph TD
    Config[pydantic-settings: ALOSSettings] --> Core[ALOS Core Engine]
    Core --> Log[structlog: JSON Event Logger]
    Core --> Retry[tenacity: Retry Decorators]
    Core --> Cache[diskcache / cachetools: LRU & Disk Cache]
    CLI[typer + rich: ALOS CLI] --> Core
```

## Technical Decisions
- Use `pydantic-settings` to replace custom parsing in `alos/core/config.py`.
- Use `structlog` to standardize logging across `alos/logs/`.
- Use `tenacity` for retries on HTTP and database connections.
