# Adopt Open-Source Dependencies for ALOS Core Architecture

* Status: accepted
* Deciders: ALOS Core Engineering Team
* Date: 2026-08-01

Technical Story: ALOS Architecture Refactoring & Vendor Dependency Optimization

## Context and Problem Statement

Following initial ALOS core feature implementation, several sub-systems relied on custom-built implementations for standard capabilities, including YAML frontmatter parsing, graph traversal, document relevance ranking, Model Context Protocol integration, and background job scheduling. Maintenance of hand-rolled implementations increases security and edge-case risk while duplicating standard library features.

Should ALOS transition from custom reimplementations to standard, mature open-source Python dependencies?

## Decision Drivers

* Reduction of custom code volume and long-term maintenance overhead.
* Adoption of battle-tested security, edge-case handling, and performance optimizations.
* Strict adherence to ALOS protocol abstractions (DIP, ISP) to ensure zero breaking changes.
* Maintenance of fast, offline-capable unit testing suites (`18/18` passing tests).

## Considered Options

* **Option 1**: Retain custom hand-rolled implementations in memory and parsing modules.
* **Option 2**: Replace custom implementations with open-source vendor dependencies (`python-frontmatter`, `networkx`, `rank-bm25`, `mcp`, `apscheduler`).

## Decision Outcome

Chosen option: **Option 2**, because replacing custom reimplementations with standard dependencies reduces code complexity while maintaining exact contract compatibility across ALOS core protocols.

### Positive Consequences

* Robust YAML frontmatter parsing via `python-frontmatter`.
* Performant graph algorithms (neighborhood, subgraphs) via `networkx`.
* Probabilistic Okapi BM25 document ranking via `rank-bm25`.
* Official protocol standards adherence via Anthropic `mcp` SDK.
* Background cron and interval scheduling via `apscheduler`.

### Negative Consequences

* Slight increase in external python package dependencies in `pyproject.toml`.

## Pros and Cons of the Options

### Option 1: Retain Custom Hand-Rolled Implementations

* Good, because no new external dependencies are added.
* Bad, because hand-rolled parsers miss edge cases and lack standard optimizations.
* Bad, because naive keyword counting in memory search is inefficient compared to BM25 or vector search.

### Option 2: Replace Custom Implementations with Vendor Dependencies

* Good, because standard dependencies have higher test coverage, community maintenance, and performance optimizations.
* Good, because DIP interfaces isolate vendor implementations from the rest of the system.
* Bad, because dependency versions must be managed via `pyproject.toml` and `uv.lock`.

## Links

* Refined by Implementation Plan in Brain Memory.
