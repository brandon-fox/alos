# Architecture Plan: Quality Gates, Linting & Security (Spec 16)

```mermaid
graph LR
    Commit[Git Commit] --> PreCommit[.pre-commit-config.yaml]
    PreCommit --> Ruff[Ruff Check & Format]
    PreCommit --> Mypy[Mypy Strict Type Check]
    PreCommit --> Bandit[Bandit Security Audit]
    PreCommit --> Sonar[Sonar Quality Gate]
```

- Configure `bandit` and `pip-audit` in `.pre-commit-config.yaml`.
- Enforce `enable_error_code = ["ignore-without-code"]` in `pyproject.toml`.
