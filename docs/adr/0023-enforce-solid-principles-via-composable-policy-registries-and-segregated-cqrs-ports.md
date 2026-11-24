# Enforce SOLID Principles via Composable Policy Registries and Segregated CQRS Ports

* Status: accepted
* Deciders: Brandon Fox
* Date: 2026-11-24

Technical Story: `specs/036-hexagonal-twelve-factor-refactor/spec.md`

## Context and Problem Statement

ALOS exhibits concrete SOLID violations across its core modules: `ALOSStateGraph` (`alos/core/graph.py`) conflates DI wiring, dual-loop orchestration, string formatting, and unconditional MCP dispatch--causing a Constitution Article V bug where `RiskLevel.HIGH` actions execute without checking `eval_result.requires_approval` (SRP); `PlannerNode`, `RuleValidator`, and `N8nClient` hardcode closed `if/elif` chains for intents, vault preferences, and workflow IDs (OCP); `LocalVectorStore` vs `SpecRAGIndexer` return incompatible dict schemas and `FallbackBM25Indexer` scores non-matches at `0.1` instead of `0.0` (LSP); `DecisionLoggerProtocol.log_decision` forces 10 primitive arguments and unsegregated read/write interfaces (ISP); and `ALOSStateGraph`, `ContextAssembler`, `RiskClassifier`, and `SafetyEvaluatorTool` instantiate concrete adapters directly, dropping Decision Logs during CrewAI safety checks (DIP). How should ALOS enforce SOLID across all layers?

## Decision Drivers

* Decompose multi-responsibility classes (`ALOSStateGraph`, `EvaluatorNode`, `ContextAssembler`, `N8nClient`, `SpecRAGIndexer`) so every class has one reason to change and Cyclomatic Complexity stays `<= 12`.
* Enable open extension of preference rules, correction rules, planner strategies, n8n workflow validators, and MCP tool handlers without editing core orchestrators.
* Guarantee behavioral substitutability across Rust PyO3 vs pure-Python fallbacks and across local vs database/RAG implementations.
* Segregate read vs write ports (CQRS) and collapse multi-argument protocol methods onto typed Pydantic value objects.
* Enforce constructor Dependency Inversion and close the `RiskLevel.HIGH` human-approval gate gap via an explicit `HumanApprovalGatePort`.

## Considered Options

* Option 1: Structural `typing.Protocol` CQRS Port Segregation + Strategy/Specification Policy Registries + Explicit Constructor Injection in a Bootstrap Composition Root
* Option 2: Third-party IoC container framework (`dependency-injector` or `injector`) with `abc.ABC` inheritance hierarchies and `@inject` decorators
* Option 3: Functional module-level higher-order callables and dictionary dispatch tables without protocol interfaces or service classes

## Decision Outcome

Chosen option: "Option 1: Structural `typing.Protocol` CQRS Port Segregation + Strategy/Specification Policy Registries + Explicit Constructor Injection in a Bootstrap Composition Root", because Python `Protocol` interfaces keep the domain and application layers zero-dependency and `mypy`-verified, strategy registries make policy and tool extension additive (OCP), and explicit constructor wiring avoids magic runtime reflection while keeping tests trivial to stub.

### Positive Consequences

* Fixes the Constitution Article V `HIGH`-risk approval bypass (`HumanApprovalGatePort`) and ensures CrewAI `SafetyEvaluatorTool` records Decision Logs via injected `EvaluateActionUseCase`.
* Removes `PLR0913`/`PLR0917` pressure on `DecisionLoggerProtocol` by passing a single `DecisionRecord` model and aligns `MemoryStoreProtocol` on a unified `RAGDocument` return contract.
* Unifies risk classification and BM25 fallback behavior across `alos_native` Rust bindings and pure-Python adapters (LSP).

### Negative Consequences

* Increases the number of focused, small modules (mitigated by clear package grouping and re-export facades).
* Requires assembling default adapter graphs in `alos/config/bootstrap.py` rather than scattering lazy imports inside constructors.

## Pros and Cons of the Options

### Option 1: Structural `typing.Protocol` CQRS Ports + Strategy Registries + Explicit Bootstrap DI

* Good, because `mypy` validates structural conformance statically without forcing adapters (or PyO3 classes) to inherit from Python ABCs.
* Good, because new `PolicyRule`, `ActionDraftStrategy`, or `ToolHandler` implementations register cleanly without touching `EvaluateActionUseCase` or `DualLoopOrchestrator`.
* Bad, because constructor wiring code must be maintained explicitly in `bootstrap.py`.

### Option 2: Third-party IoC container (`dependency-injector` / `injector`) with `abc.ABC`

* Good, because provider scopes (singleton vs factory) are declared declaratively.
* Bad, because container decorators leak framework imports into domain/application code, complicate `mypy` type inference, and add an unnecessary third-party runtime dependency.

### Option 3: Functional closures and dictionary dispatch tables only

* Good, because boilerplate for single-method interfaces is minimal.
* Bad, because multi-method cohesive contracts (`VaultReaderPort`, `DbUnitOfWorkPort`, `TelemetryPort`) lose named structural documentation and lifecycle grouping.

## Links

* Refines [ADR-0002](0002-use-model-context-protocol-for-external-integrations.md)
* Refines [ADR-0004](0004-implement-dual-loop-reasoning-core-with-safety-matrix-gate.md)
* Refines [ADR-0012](0012-use-pyo3-and-maturin-for-rust-native-performance-extensions.md)
* Complements [ADR-0022](0022-standardize-configuration-on-pydantic-settings-and-domain-data-on-frozen-pydantic-v2-models.md)
