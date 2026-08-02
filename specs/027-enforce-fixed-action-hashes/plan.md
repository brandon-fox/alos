# Architecture & Implementation Plan: Enforce Fixed Action Hashes

**Feature Branch**: `027-enforce-fixed-action-hashes`
**Status**: Approved

---

## Technical Architecture & Component Matrix

```
.github/workflows/
├── auto-merge.yml                   # Update action tags to 40-char SHA
├── code-review-bot.yml              # Update action tags to 40-char SHA
├── performance-benchmark.yml        # Update action tags to 40-char SHA
├── post-merge-pipeline.yml          # Update action tags to 40-char SHA
├── pr-title-lint.yml                # Update action tags to 40-char SHA
├── quality-gate.yml                 # Update action tags to 40-char SHA
├── release-packaging.yml            # Update action tags to 40-char SHA
├── rust-ci.yml                      # Update action tags to 40-char SHA
├── scheduled-dependency-health.yml  # Update action tags to 40-char SHA
├── scheduled-matrix-test.yml        # Update action tags to 40-char SHA
├── scheduled-stale-cleanup.yml      # Update action tags to 40-char SHA
├── security-compliance.yml          # Update action tags to 40-char SHA
├── spec-analyzer-bot.yml            # Update action tags to 40-char SHA
└── speckit-governance.yml           # Update action tags to 40-char SHA

tests/
└── test_github_workflows.py         # Add test_all_github_actions_use_fixed_hashes
```

---

## TDD Verification Strategy

1. **RED**: Add `test_all_github_actions_use_fixed_hashes` to `tests/test_github_workflows.py` asserting that all `uses: action@ref` have 40-hex SHAs. Run `pytest` to confirm failure.
2. **GREEN**: Replace all action tags across `.github/workflows/*.yml` with verified 40-character commit SHAs + tag comments. Run `pytest` to confirm success.
3. **QUALITY**: Verify `ruff check`, `mypy`, and `bandit`.
