# Standardize Configuration on Pydantic Settings and Domain Data on Frozen Pydantic v2 Models

* Status: accepted
* Deciders: Brandon Fox
* Date: 2026-11-24

Technical Story: `specs/036-hexagonal-twelve-factor-refactor/spec.md`

## Context and Problem Statement

Constitution Article I requires Pydantic v2 validation across all action inputs and outputs, yet `ALOSConfig` (`alos/core/config.py`) inherits `BaseModel` with manual `os.getenv` lambdas instead of `pydantic_settings.BaseSettings` (ignoring `.env` files), `LocalLLMConfig` (`alos/crews/config.py`) is an untyped plain class, `N8nExecutionResponse` (`alos/integrations/n8n_client.py`) is a mutable `@dataclass`, none of the 14 `BaseModel` classes set `ConfigDict(frozen=True, extra="forbid")` (`EvaluationResult` uses mutable `= []` defaults), and core boundaries (`DecisionLogger`, `SystemAuditLogger`, `MCPGateway`, `ContextPayload`, `MemoryStoreProtocol`) exchange raw `dict[str, Any]` payloads. Meanwhile, `alos/swarm/{dispatcher,sandbox}.py` must remain standard-library-only per Specs 029 and 030. What configuration and schema standard should govern all ALOS boundaries?

## Decision Drivers

* Centralize every environment variable (`ALOS_*`, `DATABASE_URL`, `REDIS_*`, `N8N_*`, `OLLAMA_*`, `SecretStr` API keys) into one validated `BaseSettings` hierarchy with `.env` loading and zero import-time side effects.
* Enforce immutability (`frozen=True`), strict unknown-field rejection (`extra="forbid"`), and `Literal` discriminated unions across all domain entities, value objects, and port DTOs.
* Replace raw `dict[str, Any]` payloads in audit logs, decision records, MCP tool envelopes, and RAG search hits with strict Pydantic v2 models.
* Preserve stdlib-only isolation inside `alos/swarm/{dispatcher,sandbox}.py` (Specs 029/030) and mutable span status assignment inside `TelemetryTracer.span()`.

## Considered Options

* Option 1: Hierarchical `pydantic-settings` (`ALOSSettings`) + Frozen Pydantic v2 Value Objects (`ConfigDict(frozen=True, extra="forbid")`) with `ALOSConfig` shim and adapter-boundary swarm wrappers
* Option 2: Python stdlib `@dataclass(frozen=True)` paired with `dynaconf` or `python-dotenv` + `dacite` runtime dictionary casting
* Option 3: `msgspec.Struct` or `attrs` schemas paired with custom `os.environ` parsing helpers

## Decision Outcome

Chosen option: "Option 1: Hierarchical `pydantic-settings` (`ALOSSettings`) + Frozen Pydantic v2 Value Objects (`ConfigDict(frozen=True, extra="forbid")`) with `ALOSConfig` shim and adapter-boundary swarm wrappers", because `pydantic` v2 is already mandated by the ALOS Constitution (`Technology Constraints`), `pydantic-settings` is already locked in `uv.lock`, and Rust-backed `pydantic-core` validators provide native JSON Schema generation for MCP tools alongside strict compile/runtime safety.

### Positive Consequences

* Eliminates scattered `os.getenv` calls, credential mismatches between `.env.example` and `config.py`, and silent schema drift across `DecisionRecord`, `AuditEvent`, `RAGDocument`, and `ActionPlan`.
* Catches malformed tool arguments and unknown fields at boundary deserialization (`extra="forbid"`) while keeping domain objects hashable and side-effect-free (`frozen=True`).
* Preserves backwards compatibility for `ALOSConfig`, `SpanContext` (`validate_assignment=True`), and stdlib-only `alos.swarm` workers.

### Negative Consequences

* Declares `pydantic-settings>=2.0.0` (and `pyyaml>=6.0.0`) explicitly in `pyproject.toml` runtime dependencies.
* Requires thin `.to_dict()` / `model_dump()` compatibility helpers where legacy callers or `langgraph` `TypedDict` state channels expect dictionaries.

## Pros and Cons of the Options

### Option 1: Hierarchical `pydantic-settings` + Frozen Pydantic v2 Value Objects

* Good, because it satisfies Constitution Article I directly using Rust-accelerated `pydantic-core` validation and native `.model_json_schema()` export for MCP tools.
* Good, because `BaseSettings` supports `env_prefix`, `AliasChoices`, `SecretStr`, `.env` files, and `monkeypatch.setenv` dynamically at instantiation time.
* Bad, because `alos.swarm` stdlib worker dataclasses must be mapped at the outbound adapter boundary rather than importing Pydantic inside `dispatcher.py` or `sandbox.py`.

### Option 2: Stdlib `@dataclass(frozen=True)` + `dynaconf` or `python-dotenv` + `dacite`

* Good, because domain models use stdlib syntax.
* Bad, because it violates the Constitution mandate for Pydantic v2 schemas on all action payloads and lacks built-in coercions, `SecretStr`, and JSON Schema generation.

### Option 3: `msgspec.Struct` or `attrs` schemas with custom `os.environ` parsing

* Good, because `msgspec` offers fast JSON serialization.
* Bad, because it introduces a competing schema library alongside `pydantic` (`mcp` and `langgraph` already depend on Pydantic v2) and lacks mature `.env` settings hierarchy tooling.

## Links

* Refines [ADR-0004](0004-implement-dual-loop-reasoning-core-with-safety-matrix-gate.md)
* Refines [ADR-0009](0009-adopt-open-source-dependencies-for-alos-core-architecture.md)
* Complements [ADR-0021](0021-adopt-twelve-factor-application-alignment-and-constitutional-provenance-harmonization.md)
