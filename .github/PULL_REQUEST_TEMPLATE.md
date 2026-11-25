## Summary & Rationale
<!-- Concise explanation of what changed and why. Keep PRs within 200-400 non-lockfile lines (<=1000 hard limit). -->

## Governance & Traceability
- **SpecKit Feature**: `specs/NNN-feature-name/` *(or `N/A — docs/chore/deps`)*
- **ADR Reference**: `docs/adr/NNNN-*.md` *(or `N/A`)*
- **Risk Tier**: `LOW` | `MEDIUM` | `HIGH`
- **Breaking Change**: `No` | `Yes (describe migration)`

## Pre-Merge Verification Checklist
- [ ] Commits are SSH/GPG signed (`git log -n 1 --show-signature`) and branch uses an allowed prefix (`feat/`, `fix/`, `chore/`, `docs/`, `ci/`, `refactor/`, `test/`, `build/`, `perf/`, `stack/`)
- [ ] Unit, meta, and `@mocked` + `@live` BDD scenarios added/updated (`>= 90%` branch coverage)
- [ ] `ruff check`, `mypy`, `bandit`, `mkdocs build --strict`, and `pyadr check-adr-repo` pass cleanly with zero unjustified suppressions
