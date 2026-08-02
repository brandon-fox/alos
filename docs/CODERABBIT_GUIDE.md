# CodeRabbit Integration & Power User Guide

This guide details how to get maximum value from **CodeRabbit AI** in the ALOS repository. CodeRabbit acts as an automated AI reviewer integrated directly into GitHub Pull Requests, working alongside pre-commit hooks, pre-push verification gates, and GitHub Actions CI pipelines.

---

## 1. Overview & Architecture

CodeRabbit is configured via [`.coderabbit.yaml`](file:///c:/Users/bfoxt/n8nSetup/.coderabbit.yaml) in the repository root. It enforces project rules, SpecKit compliance, type safety, and security audits automatically on every PR targeting `main` or `upstream/main`.

### Integrated Quality Stack:
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                             Pull Request Opened                             │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                    ┌──────────────────┴──────────────────┐
                    ▼                                     ▼
      ┌───────────────────────────┐         ┌───────────────────────────┐
      │     GitHub Actions CI     │         │       CodeRabbit AI       │
      ├───────────────────────────┤         ├───────────────────────────┤
      │ • Quality Gate (Ruff/Mypy)│         │ • Line-by-line AI Review  │
      │ • Bandit Security Audit   │         │ • SpecKit Traceability    │
      │ • Pytest & BDD Suite      │         │ • Fix-First Enforcement   │
      │ • Sonar Quality Gate      │         │ • Automated PR Walkthrough│
      └───────────────────────────┘         └───────────────────────────┘
```

---

## 2. Repository-Tailored CodeRabbit Directives

CodeRabbit evaluates PRs against explicit path-based rules configured in `.coderabbit.yaml`:

1. **Python Quality (`alos/**/*.py`)**:
   - Strictly enforces type annotations (mypy compatibility).
   - Validates the **Fix-First Policy**: Disallows bare `# noqa` or `# type: ignore` without specific error codes and inline justification comments.
   - Audits error handling to prevent swallowed exceptions or missing root cause logging.

2. **SpecKit SDD Compliance (`specs/**`)**:
   - Verifies standard SpecKit structure (`specs/<N>-<feature-name>/` containing `spec.md`, `plan.md`, `tasks.md`, and `checklists/requirements.md`).
   - Verifies requirement ID formatting (e.g. `FR-XXX`) and task mapping.

3. **Architectural Decision Records (`docs/adr/**`)**:
   - Ensures ADRs follow `pyadr` CLI conventions and are not manually edited outside management rules.

4. **Testing Standards (`tests/**`)**:
   - Validates Red-Green-Refactor compliance and BDD scenario mapping between `.feature` files and step definitions.

5. **Rust Crates (`crates/**/*.rs`)**:
   - Ensures memory safety, explicit error propagation (`Result`/`Option`), and clean PyO3 FFI boundaries.

---

## 3. Pull Request Interaction & Slash Commands

You can interact directly with CodeRabbit in any PR conversation by leaving a comment starting with `@coderabbitai`.

| Slash Command | Description | Example Usage |
| :--- | :--- | :--- |
| `@coderabbitai review` | Triggers an incremental review of new changes since the last review. | `@coderabbitai review` |
| `@coderabbitai full review` | Forces a full re-review of all modified files in the PR. | `@coderabbitai full review` |
| `@coderabbitai summary` | Regenerates the high-level PR summary, change categorization, and sequence diagram. | `@coderabbitai summary` |
| `@coderabbitai ask <question>` | Asks CodeRabbit a specific question about the PR code, architecture, or edge cases. | `@coderabbitai ask How does this handle concurrency under high load?` |
| `@coderabbitai generate docstrings` | Automatically generates clean docstrings for modified classes and methods. | `@coderabbitai generate docstrings` |
| `@coderabbitai resolve` | Resolves all CodeRabbit review threads that have been addressed. | `@coderabbitai resolve` |
| `@coderabbitai pause` | Temporarily disables automated review triggers on the current PR. | `@coderabbitai pause` |
| `@coderabbitai resume` | Resumes automated reviews for subsequent commits on the PR. | `@coderabbitai resume` |

---

## 4. Best Practices for Developers & AI Agents

1. **Leverage Sequence Diagrams**:
   - Review the automatically generated Mermaid sequence diagrams in CodeRabbit's PR summary to verify control flow and component interaction.

2. **Fix Issues at the Source**:
   - CodeRabbit will flag any missing justification comments on `# type: ignore` or `# noqa`. Always resolve underlying type errors or add explicit explanations as required by the **Fix-First Directive**.

3. **Interactive Test Generation**:
   - Reply to a line comment from `@coderabbitai` with: `@coderabbitai write unit tests for this function covering edge cases` to get tailored pytest code snippets.

4. **Interactive Code Refactoring**:
   - If CodeRabbit notes a potential complexity smell or Sonar issue, comment `@coderabbitai suggest a refactoring using clean Python 3.12 idioms` to evaluate alternative designs.

---

## 5. Rate Limit & OSS Quota Optimization Strategy

If CodeRabbit encounters rate limits or quota exhaustion on Open Source / free tiers, apply these configuration strategies:

1. **Path Filters (Ignore High-Volume Files)**:
   - Exclude markdown files (`!**/*.md`), specs (`!specs/**`), docs (`!docs/**`), workflows (`!.github/**`), lockfiles, and JSON/YAML templates in `.coderabbit.yaml`.
   - Ensures CodeRabbit ONLY consumes LLM tokens when core application source code (`alos/**/*.py`, `crates/**/*.rs`) changes.

2. **Disable Token-Intensive Features**:
   - Set `sequence_diagrams: false` to skip heavy multi-step LLM sequence graph generation per commit.
   - Set `collapse_walkthrough: true` to generate compact summary output.
   - Set `profile: "chill"` for concise, low-token review comments.

3. **Disable Redundant Linters**:
   - Disable secondary linters in CodeRabbit (`actionlint`, `markdownlint`, `ast-grep`) if they already run in GitHub Actions CI.

4. **Label-Based or Manual Triggers (Extreme Quota Saving)**:
   - If auto-review still hits rate limits, change `auto_review.enabled: false` in `.coderabbit.yaml` and trigger reviews on demand by leaving `@coderabbitai review` on open PRs.

---

## 6. Recommended CodeRabbit Web App & GitHub Settings

To maximize integration across GitHub:

1. **Branch Protection Enforce Check**:
   - In GitHub Repository Settings -> **Branches** -> **Branch protection rules for `main`**:
   - Enable **"Require status checks to pass before merging"** and add `CodeRabbit` to the required checks.

2. **SonarCloud / Linter Integrations**:
   - Ensure CodeRabbit integrations are authorized in the CodeRabbit Web App Dashboard to read native CI status checks for unified feedback.

3. **Automated Release Notes**:
   - Enable CodeRabbit's release notes generator to automatically draft release summaries upon merging PRs into `main`.
