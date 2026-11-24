# Architecture & Requirements Quality Checklist: Twelve-Factor, Pydantic v2, SOLID & Hexagonal Refactor

**Purpose**: Validate specification completeness, clarity, consistency, PR slicing, doc/comment governance, and overnight `/swarm` readiness ("Unit Tests for Requirements")
**Created**: 2026-11-24
**Feature**: [spec.md](../spec.md) | [plan.md](../plan.md) | [tasks.md](../tasks.md)

## Requirement Completeness

- [x] CHK001 Are all twelve Twelve-Factor principles mapped to explicit functional requirements or documented constitutional harmonizations? [Completeness, Spec §FR-3601, §FR-3602, §FR-3612..FR-3615]
- [x] CHK002 Are runtime settings requirements specified for every `.env.example` variable group (Database, Redis, n8n, Vault/Logs, LLM secrets)? [Completeness, Spec §FR-3602]
- [x] CHK003 Are immutability and unknown-field rejection rules specified across all domain entities, actions, provenance events, and RAG models? [Completeness, Spec §FR-3603]
- [x] CHK004 Are all five SOLID principles (SRP, OCP, LSP, ISP, DIP) addressed by testable architectural requirements? [Completeness, Spec §FR-3605..FR-3609]
- [x] CHK005 Are module/class/function docstring requirements, inline architectural/ring design comments, and documentation/diagram refresh targets (`docs/architecture.md`, `README.md`, `docs/getting_started.md`, `docs/specs_setup.md`, `docs/traceability.md`) explicitly specified? [Completeness, Spec §FR-3617, §FR-3618]

## Requirement Clarity & Measurability

- [x] CHK006 Is the distinction between Factor XI diagnostic event streams (`stdout`/`stderr`) and Factor IV Constitutional provenance ledgers (`decision_log.jsonl`, `system_audit.jsonl`, PostgreSQL) unambiguous? [Clarity, Spec §FR-3612, ADR-0021]
- [x] CHK007 Are quantitative PR slice and CI/post-merge thresholds (`200-400` target LOC/PR, `<= 1,000` hard cap, `>= 90%` test coverage, `>= 75%` MyPy file precision, `CC <= 10`, `0` missing docstrings, `0` debt markers) explicitly quantified? [Measurability, Spec §FR-3616, §FR-3617, §SC-004]
- [x] CHK008 Is `RiskLevel.HIGH` approval gating behavior clearly specified prior to `MCPGatewayProtocol` invocation? [Clarity, Spec §FR-3609, §SC-003]

## Consistency & Constitutional Alignment

- [x] CHK009 Do `EmailDraft` (`HIGH`) and `EmailSend` (`HIGH`) risk classifications remain consistent with existing Safety Matrix BDD contracts? [Consistency, Spec §US2, Plan §PR-04]
- [x] CHK010 Is the exception for assignment-validated `SpanContext` (`validate_assignment=True`) consistent with active `tracer.span()` usage? [Consistency, Spec §FR-3604]
- [x] CHK011 Does the specification preserve Specs 029/030 standard-library-only isolation inside `alos/swarm/{dispatcher,sandbox}.py` and First-ADE `A1/A8/A9` invariants in `README.md`? [Consistency, Spec §FR-3615, §FR-3618]
- [x] CHK012 Are all four ADR references (`ADR-0021`..`ADR-0024`) accepted and present in `docs/adr/`? [Traceability, Spec §Header]

## Stacked PRs, Overnight `/swarm` & CI Risk Coverage

- [x] CHK013 Are both `@mocked` and `@live` BDD verification scenarios required for each `200-400` LOC PR increment? [Coverage, Spec §FR-3616]
- [x] CHK014 Are Strangler-Fig re-export shims preserved across intermediate stacked PRs so existing tests and Alembic never break? [Coverage, Spec §FR-3611]
- [x] CHK015 Are GitHub Stack child-PR protections (`--draft --label wip` to prevent `auto-merge.yml` squashing into parent branches, plus `git rebase --update-refs --onto origin/main` promotion) explicitly defined? [Edge Cases, Plan §Overnight `/swarm` Execution]
- [x] CHK016 Are `/swarm` worker file boundaries, `workspace:"share"` vs `"inherit"` assignments, `stack-shepherd` serialization, and active local worktree/bot deconfliction specified? [Dependencies, Plan §16-PR Granular Stack & Wave Plan]

## Notes

- Validated 16/16 requirement quality checks PASS with zero unresolved `[NEEDS CLARIFICATION]` markers.
