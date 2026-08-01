---
name: git-commit-and-push
description: Embedded repo skill for making atomic, signed git commits early and often ("more is better"), enforcing strict git isolation and hygiene, and pushing feature branches.
---

# Git Atomic Commit & Push Skill

This skill governs all source control mutation workflows in this repository. The Git tree is an immutable ledger of decisions, context, and tested incremental progress.

---

## CORE MANDATES

1. **Commit Cadence ("More is Better")**:
   - Commit early and often. Every passing unit test, completed task, architectural decision, or incremental piece of verified code MUST be committed immediately.
   - Do NOT stack large multi-file refactors or multiple features into a single commit.

2. **Strict Git Isolation (Multi-Agent Safety)**:
   - **STRICTLY FORBIDDEN**: `git add .`, `git add -A`, `git commit -a`.
   - **MANDATORY**: Explicitly stage ONLY the files created or modified for the specific atomic change:
     ```bash
     git add path/to/file1.py path/to/test_file1.py
     ```

3. **Mandatory Commit Signing**:
   - All commits MUST have verified SSH or GPG signatures.
   - SSH signing configuration MUST use workspace `.ssh/*.pub` keys (`gpg.format=ssh` and `user.signingkey`).
   - Never default to extraneous service keys (e.g. `.ollama`).

4. **Git Hygiene & Cache Prevention**:
   - Verify un-tracked and ignored files before committing using `git status -s` and `git ls-files --others`.
   - Ensure temporary logs (`*.log`), scratch files (`scratch/`), python cache (`**/__pycache__/`, `*.pyc`), and virtual environment artifacts are un-tracked.

---

## STEP-BY-STEP COMMIT WORKFLOW

### Step 1: Pre-Commit Quality & Validation
Before staging files, ensure all pre-commit hooks and checks pass:
```powershell
uv run ruff check alos tests
uv run ruff format alos tests
uv run mypy alos
uv run pytest
```

### Step 2: Hygiene Audit
Check untracked and modified files to guarantee no unwanted cache or temporary files are staged:
```powershell
git status -s
git ls-files --others
```

### Step 3: Atomic File Staging
Explicitly stage ONLY the relevant files for this atomic commit:
```powershell
git add <path/to/file1> <path/to/file2>
```

### Step 4: Formulate Commit Message & Commit
Commit messages MUST follow the Conventional Commits specification and include explanatory body context detailing **what** changed and **why**:

```powershell
git commit -m "feat(scope): short summary of atomic change

- Detailed bullet point explaining rationale or decision
- Additional context regarding tested implementation details"
```

#### Commit Message Types:
- `feat`: New capability, subagent, or user-facing feature.
- `fix`: Bug fix, patch, or error resolution.
- `chore`: Infrastructure, dependency update, pre-commit config, or workspace setup.
- `docs`: Documentation, spec, or ADR updates.
- `test`: Adding or updating unit/BDD tests.
- `refactor`: Restructuring existing code without behavior changes.

### Step 5: Push Feature Branch
Ensure you are on a feature branch (e.g., `feat/...`, `fix/...`, `chore/...`) branched off `upstream/main`:
```powershell
git push origin <branch-name>
```

> [!NOTE]
> **Auth Failure Fallback**: If `git push` returns `403 Forbidden`, update the remote URL to include the explicit username:
> `git remote set-url origin https://<username>@github.com/<owner>/<repo>.git`
