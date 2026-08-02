---
name: "gha-pipeline-optimization"
description: "Guidelines and reference procedures for auditing, grouping, and optimizing GitHub Actions workflows, caching, path filtering, and bot reviews."
---

# GitHub Actions Pipeline Optimization Skill

## Overview

This skill provides reference guidelines for maintaining, auditing, and optimizing the GitHub Actions CI/CD workflows in this repository.

## Key Architectural Principles

1. **Path Filtering Isolation**:
   - Python workflows (`quality-gate.yml`) use `dorny/paths-filter@v3` to only run Python quality checks (`ruff`, `mypy`, `bandit`, `pytest`) when Python files (`alos/**`, `tests/**`, `pyproject.toml`, `uv.lock`) are changed.
   - Rust workflows (`rust-ci.yml`) run independently when native Rust files (`crates/**`, `Cargo.lock`) are modified.
   - Saves runner minutes and avoids unnecessary CI failures when editing unrelated sub-components.

2. **High-Performance Caching**:
   - **Python Dependencies**: Uses `astral-sh/setup-uv@v5` with `enable-cache: true`.
   - **Rust Build Artifacts**: Uses `Swatinem/rust-cache@v2` targeting `crates/alos_native`.
   - **Open-Source AI Model Weights**: Uses `actions/cache@v4` targeting `~/.cache/huggingface/hub` and `~/.cache/torch/hub` (caching up to 2GB of model weights for fast local evaluation).

3. **Consolidated Post-Merge Pipeline**:
   - All post-merge analysis tasks (SonarCloud scan, changelog generation, complexity scanning, coverage gap analysis, docstring audits, spec gap analysis, tech debt harvesting, and type coverage reports) are consolidated in `.github/workflows/post-merge-pipeline.yml`.

4. **In-Place Bot Review PR Comments**:
   - `Spec Review Bot` (`spec-analyzer-bot.yml`) and `AI Code Review Bot` (`code-review-bot.yml`) post structured Markdown feedback on PRs.
   - Both bots look for unique HTML comment markers (`<!-- spec-analyzer-bot-comment -->` and `<!-- ai-code-review-bot-comment -->`) and update existing comments in-place instead of creating duplicate comments on subsequent commits.

## Maintenance Checklist

- [ ] Check `astral-sh/setup-uv` and `actions/cache` versions for updates.
- [ ] Ensure any newly added language/framework sub-directories are added to `dorny/paths-filter@v3` triggers in `quality-gate.yml`.
- [ ] Verify that model weight caching paths include any new cache directories when adding new LLM/embedding frameworks.
