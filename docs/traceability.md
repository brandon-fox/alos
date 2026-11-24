# Traceability

> Generated 2026-11-24 by `scripts/traceability.py` from `specs/`, `tests/features/` and `docs/adr/`. Regenerate rather than edit. A feature with no acceptance file is a gap, listed as `none`; 18 of 35 specs have no matched feature file today.

A feature file that opens with a comment of the form `# spec: NNN-slug` is matched to that spec outright. Otherwise matching is by shared slug words (two words, or one word of seven or more letters); a row marked `none` may have coverage under a different name. The honest reading is the gap count, not the match count.

| Spec | spec.md | plan.md | tasks.md | Acceptance feature | ADR |
| --- | --- | --- | --- | --- | --- |
| [001-fix-ci-pyadr](../specs/001-fix-ci-pyadr/) | yes | yes | yes | none | none |
| [002-crewai-local-orchestration](../specs/002-crewai-local-orchestration/) | yes | yes | yes | none | none |
| [003-rust-core-architectural-refactor](../specs/003-rust-core-architectural-refactor/) | yes | yes | yes | none | [0013-adopt-rust-native-core-engine-and-p](adr/0013-adopt-rust-native-core-engine-and-pre-refactor-test-fortification-architecture.md) |
| [004-rust-native-perf](../specs/004-rust-native-perf/) | yes | yes | yes | none | [0012-use-pyo3-and-maturin-for-rust-nativ](adr/0012-use-pyo3-and-maturin-for-rust-native-performance-extensions.md) |
| [005-fix-all-github-issues](../specs/005-fix-all-github-issues/) | yes | yes | yes | none | none |
| [006-context-synthesis](../specs/006-context-synthesis/) | yes | yes | yes | [01_context_synthesis.feature](../tests/features/01_context_synthesis.feature) | none |
| [007-dual-loop-reasoning](../specs/007-dual-loop-reasoning/) | yes | yes | yes | [02_dual_loop_reasoning.feature](../tests/features/02_dual_loop_reasoning.feature) | [0004-implement-dual-loop-reasoning-core-](adr/0004-implement-dual-loop-reasoning-core-with-safety-matrix-gate.md) |
| [008-safety-matrix](../specs/008-safety-matrix/) | yes | yes | yes | [03_safety_matrix.feature](../tests/features/03_safety_matrix.feature) | [0004-implement-dual-loop-reasoning-core-](adr/0004-implement-dual-loop-reasoning-core-with-safety-matrix-gate.md) |
| [009-mcp-integrations](../specs/009-mcp-integrations/) | yes | yes | yes | [04_mcp_integrations.feature](../tests/features/04_mcp_integrations.feature) | none |
| [010-audit-and-decision-log](../specs/010-audit-and-decision-log/) | yes | yes | yes | [05_audit_logging.feature](../tests/features/05_audit_logging.feature) | none |
| [011-rag-and-knowledge-base](../specs/011-rag-and-knowledge-base/) | yes | yes | yes | [06_rag_knowledge_base.feature](../tests/features/06_rag_knowledge_base.feature) | none |
| [012-postgres-orm-migrations](../specs/012-postgres-orm-migrations/) | yes | yes | yes | [07_postgres_orm_migrations.feature](../tests/features/07_postgres_orm_migrations.feature) | [0007-adopt-sqlalchemy-orm-and-alembic-fo](adr/0007-adopt-sqlalchemy-orm-and-alembic-for-postgresql-data-models-and-migrations.md) |
| [013-obsidian-vault-brain-integration](../specs/013-obsidian-vault-brain-integration/) | yes | yes | yes | [08_obsidian_vault_brain.feature](../tests/features/08_obsidian_vault_brain.feature) | [0003-adopt-local-obsidian-vault-and-vect](adr/0003-adopt-local-obsidian-vault-and-vector-store-for-memory-rag.md) |
| [014-langgraph-n8n-self-reflection](../specs/014-langgraph-n8n-self-reflection/) | yes | yes | yes | [langgraph_n8n_loop.feature](../tests/features/langgraph_n8n_loop.feature) | [0010-adopt-langgraph-for-autonomous-self](adr/0010-adopt-langgraph-for-autonomous-self-reflection-loops-over-n8n-workflows.md) |
| [015-core-frameworks-and-runtime](../specs/015-core-frameworks-and-runtime/) | yes | yes | yes | [runtime_observability_monitoring.feature](../tests/features/runtime_observability_monitoring.feature) | none |
| [016-database-and-orm-evolution](../specs/016-database-and-orm-evolution/) | yes | yes | yes | none | none |
| [017-vector-store-and-rag-pipeline](../specs/017-vector-store-and-rag-pipeline/) | yes | yes | yes | none | [0003-adopt-local-obsidian-vault-and-vect](adr/0003-adopt-local-obsidian-vault-and-vector-store-for-memory-rag.md) |
| [018-agent-orchestration-and-state-graphs](../specs/018-agent-orchestration-and-state-graphs/) | yes | yes | yes | none | none |
| [019-mcp-gateways-and-protocols](../specs/019-mcp-gateways-and-protocols/) | yes | yes | yes | none | none |
| [020-observability-metrics-and-tracing](../specs/020-observability-metrics-and-tracing/) | yes | yes | yes | [observability_and_tracing.feature](../tests/features/observability_and_tracing.feature) | [0014-adopt-local-first-runtime-observabi](adr/0014-adopt-local-first-runtime-observability-metrics-tracing-and-monitoring.md) |
| [021-testing-bdd-and-qa-automation](../specs/021-testing-bdd-and-qa-automation/) | yes | yes | yes | none | none |
| [022-quality-gates-linting-and-security](../specs/022-quality-gates-linting-and-security/) | yes | yes | yes | none | none |
| [023-build-tooling-and-monorepo-workflow](../specs/023-build-tooling-and-monorepo-workflow/) | yes | yes | yes | none | none |
| [024-architectural-patterns-and-cqrs](../specs/024-architectural-patterns-and-cqrs/) | yes | yes | yes | none | none |
| [025-open-source-dual-repo-architecture](../specs/025-open-source-dual-repo-architecture/) | yes | yes | yes | none | [0009-adopt-open-source-dependencies-for-](adr/0009-adopt-open-source-dependencies-for-alos-core-architecture.md) |
| [026-github-actions-expansion](../specs/026-github-actions-expansion/) | yes | yes | yes | none | none |
| [027-speckit-lifecycle-archiving](../specs/027-speckit-lifecycle-archiving/) | yes | yes | yes | [speckit_lifecycle_archiving.feature](../tests/features/speckit_lifecycle_archiving.feature) | none |
| [028-enforce-fixed-action-hashes](../specs/028-enforce-fixed-action-hashes/) | yes | yes | yes | [enforce_fixed_action_hashes.feature](../tests/features/enforce_fixed_action_hashes.feature) | none |
| [029-local-swarm-dispatcher](../specs/029-local-swarm-dispatcher/) | yes | yes | yes | none | none |
| [030-swarm-test-sandbox](../specs/030-swarm-test-sandbox/) | yes | yes | yes | none | none |
| [031-runtime-observability-monitoring](../specs/031-runtime-observability-monitoring/) | yes | yes | yes | [runtime_observability_monitoring.feature](../tests/features/runtime_observability_monitoring.feature) | [0014-adopt-local-first-runtime-observabi](adr/0014-adopt-local-first-runtime-observability-metrics-tracing-and-monitoring.md) |
| [032-preemptible-compute-governor](../specs/032-preemptible-compute-governor/) | yes | yes | yes | [preemptible_compute_governor.feature](../tests/features/preemptible_compute_governor.feature) | [0015-adopt-preemptible-host-governor-and](adr/0015-adopt-preemptible-host-governor-and-sticky-model-epoch-queue.md) |
| [033-automatic-signed-pr-rebase](../specs/033-automatic-signed-pr-rebase/) | yes | yes | yes | [automatic_signed_pr_rebase.feature](../tests/features/automatic_signed_pr_rebase.feature) | [0017-adopt-signed-ci-pr-rebase-and-unive](adr/0017-adopt-signed-ci-pr-rebase-and-universal-auto-merge.md) |
| [034-portable-production-runtime](../specs/034-portable-production-runtime/) | yes | yes | yes | [portable_runtime.feature](../features/portable_runtime.feature) | [0018-adopt-dual-mode-portable-wheel-and-](adr/0018-adopt-dual-mode-portable-wheel-and-hardened-container-production-runtime.md) |
| [035-parallel-testing-and-qa-matrix](../specs/035-parallel-testing-and-qa-matrix/) | yes | yes | yes | none | [0020-adopt-property-fuzzing-differential](adr/0020-adopt-property-fuzzing-differential-native-verification-mutation-testing-and-dual-os-coverage-matrix.md) |
