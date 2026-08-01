---
name: pyadr-management
description: Strict guidelines and enforcement for managing Architectural Decision Records (ADRs) using the pyadr CLI tool. ALWAYS use pyadr CLI instead of creating or editing ADR markdown files manually.
---

# `pyadr` Management Skill

This skill enforces strict usage of the `pyadr` command-line tool for managing repo-level Architectural Decision Records (ADRs).

## MANDATORY DIRECTIVE
**NEVER manually craft, create, rename, or edit ADR markdown files directly in `docs/adr/`.**
All ADR operations (creation, proposal, acceptance, rejection, table-of-contents generation, and repository validation) MUST be executed using the official `pyadr` CLI tool.

---

## Allowed `pyadr` CLI Workflows

### 1. Initializing an ADR Repository
```bash
pyadr init -n
```
*Creates `docs/adr/`, installs `template.md`, and bootstraps initial records `0000` and `0001`.*

### 2. Proposing a New ADR
```bash
pyadr new "<Title Words Separate By Spaces>" -n
# OR
pyadr propose "<Title Words Separate By Spaces>" -n
```
*Generates `docs/adr/XXXX-title-in-kebab-case.md` in proposed state.*

### 3. Accepting a Proposed ADR
```bash
pyadr accept docs/adr/XXXX-title-in-kebab-case.md -n
```
*Assigns the next sequential numerical prefix (e.g. `0002-`), updates status to `accepted`, and records date.*

### 4. Rejecting a Proposed ADR
```bash
pyadr reject docs/adr/XXXX-title-in-kebab-case.md -n
```
*Assigns the next sequential numerical prefix, updates status to `rejected`, and records date.*

### 5. Generating Table of Contents Index
```bash
pyadr toc -n
```
*Automatically regenerates `docs/adr/index.md` with links to all accepted, rejected, superseded, and deprecated ADRs.*

### 6. Checking ADR Repository Health (Pre-commit / CI)
```bash
pyadr check-adr-repo -n
```
*Validates file naming conventions, status headers, numbering consistency, and index alignment.*

---

## Guidelines for AI Assistants
- When a user asks to record an architecture decision, execute `pyadr new "<title>"` followed by `pyadr accept <filepath>`.
- Use the `-n` (--no-interaction) flag for automated script execution.
- Run `pyadr toc` and `pyadr check-adr-repo` after accepting or rejecting any ADR to keep `docs/adr/index.md` in sync and passing CI checks.
