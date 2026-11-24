# Adopt Hexagonal Ports and Adapters Architecture via Strangler-Fig Incremental PRs

* Status: accepted
* Deciders: Brandon Fox
* Date: 2026-11-24

Technical Story: `specs/036-hexagonal-twelve-factor-refactor/spec.md`

## Context and Problem Statement

`alos/` currently contains three bidirectional package cycles (`alos.core <-> alos.logs`, `alos.core <-> alos.memory`, `alos.core <-> alos.integrations`) hidden behind global Ruff `PLC0415` suppression, coupling domain policies directly to filesystem, SQLAlchemy, PyO3, and MCP details. Refactoring 52 Python modules and 31 test suites simultaneously would fail the CI `PR Size Guard (<= 1000 lines)` hard limit, break test/Alembic import contracts, and create severe merge conflicts with concurrent worktrees and open Dependabot PRs. What target Hexagonal topology and incremental migration strategy should ALOS adopt?

## Decision Drivers

* Enforce strict inward-only dependency rules (`alos.domain <- alos.application <- alos.adapters <- alos.config`) verified automatically via AST meta-testing so `PLC0415` circular-import suppression can be retired.
* Keep every pull request strictly below the `<= 1000` non-lockfile line CI hard limit (targeting `200-400` lines) while maintaining `>= 90%` branch test coverage, `CC <= 10`, and all required `main` branch checks.
* Preserve 100% backwards-compatible import paths across `alos.{core,schemas,logs,memory,integrations,db,engine,crews}` during transitional PRs so existing tests and Alembic migrations never break mid-flight.
* Minimize rebase friction against concurrent feature branches touching `alos/cli.py`, `alos/db/`, `alos/logs/`, `alos/swarm/`, `pyproject.toml`, `docs/adr/`, and `specs/`.

## Considered Options

* Option 1: Four-ring Hexagonal topology (`domain/`, `application/`, `adapters/{inbound,outbound}/`, `config/`) migrated via Strangler-Fig re-export shims across stacked trunk-based PRs (`200-400` lines each) with AST boundary enforcement
* Option 2: Big-Bang single-PR cutover moving all 52 modules and updating all 31 test suites in one branch
* Option 3: Vertical feature-slice folders (`alos/features/{calendar,todoist,vault,n8n,speckit}/`) co-locating domain schemas, SQL/filesystem adapters, and CLI handlers without a unified Domain/Ports ring

## Decision Outcome

Chosen option: "Option 1: Four-ring Hexagonal topology (`domain/`, `application/`, `adapters/{inbound,outbound}/`, `config/`) migrated via Strangler-Fig re-export shims across stacked trunk-based PRs (`200-400` lines each) with AST boundary enforcement", because inward dependency rings isolate pure domain logic from I/O adapters, Strangler-Fig facades guarantee green tests on every intermediate squash-merge to `main`, and small scoped PRs satisfy `PR Size Guard` while localizing potential rebase conflicts.

### Positive Consequences

* Eliminates all bidirectional package cycles in `alos/`, keeping `alos/domain/` pure (`stdlib` + `pydantic` only) and trivially testable in microseconds without mocks or filesystem setup.
* Allows every incremental PR to merge independently to `main` via squash-merge with zero broken intermediate states.
* Protects stdlib-only `alos/swarm/{dispatcher,sandbox}.py` worker contracts (Specs 029/030) behind outbound adapter boundaries.

### Negative Consequences

* Temporarily maintains thin `__all__` re-export shims in legacy `alos/*` paths across intermediate PRs until test imports migrate in the final cleanup PR.
* Requires disciplined branch rebasing (`rebase --update-refs`) and sequential ADR/Spec ID checks as stacked PRs land on `main`.

## Pros and Cons of the Options

### Option 1: Four-ring Hexagonal topology + Strangler-Fig stacked PRs + AST boundary gate

* Good, because AST import rules mechanically prevent infrastructure leakage back into `domain/` or `application/`.
* Good, because each PR stays within `200-400` changed lines (`< 1000` hard ceiling) and rebases cleanly against `origin/main`.
* Bad, because legacy re-export shims add minor temporary file count until the final cutover PR removes or freezes them.

### Option 2: Big-Bang single-PR cutover

* Good, because no transitional re-export shims are needed.
* Bad, because a `4,000+`-line diff is blocked unconditionally by `PR Size Guard (<= 1000 lines)` and creates unmergeable conflicts with active worktrees.

### Option 3: Vertical feature-slice packaging without a shared Domain/Ports ring

* Good, because single-feature edits stay in one directory.
* Bad, because cross-cutting ALOS Constitutional invariants (`SafetyMatrix`, `DecisionRecord`, `ContextPayload`, `VaultReaderPort`) are shared across all integrations and would duplicate or cross-import across slices.

## Links

* Refines [ADR-0005](0005-enforce-speckit-sdd-bdd-and-tdd-development-paradigms.md)
* Refines [ADR-0013](0013-adopt-rust-native-core-engine-and-pre-refactor-test-fortification-architecture.md)
* Synthesizes [ADR-0021](0021-adopt-twelve-factor-application-alignment-and-constitutional-provenance-harmonization.md), [ADR-0022](0022-standardize-configuration-on-pydantic-settings-and-domain-data-on-frozen-pydantic-v2-models.md), and [ADR-0023](0023-enforce-solid-principles-via-composable-policy-registries-and-segregated-cqrs-ports.md)
