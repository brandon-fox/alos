---
name: git-tree-context-search
description: Custom repo skill for reading and searching the Git tree to extract historical rationale, decision context, evolution of code, and architectural trends before making assumptions or refactoring.
---

# Git Tree Context Search Skill

This skill governs how agents use the Git tree as an active source of historical reasoning, decision tracking, and context. Code in the workspace tells you **what** the system currently does; the Git tree reveals **why** it was designed that way and **how** it evolved.

---

## MANDATORY ACTIVATION TRIGGER

Agents **MUST** activate and use this skill:
1. **Before Refactoring or Modifying Legacy Code**: Never assume an unusual code structure or configuration is dead code or an error without checking its commit history.
2. **During Debugging or Regression Analysis**: Track when a bug or unexpected behavior was introduced and read the original commit message rationale.
3. **When Investigating Architectural Rationale**: Query past commit messages and diffs to understand trade-offs, past decisions, or feature iterations.
4. **When Determining Codebase Trends**: Inspect commit frequency, change velocity, or historical churn across modules.

---

## GIT TREE SEARCH TOOLKIT & WORKFLOWS

### 1. Searching for Code Introduction or Deletion (Pickaxe Search)
Find commits that added or removed a specific function, class, symbol, or string:
```powershell
# Pickaxe search for exact string addition/deletion
git log -S "SpecRAGIndexer" -p

# Regex pickaxe search for pattern changes
git log -G "def process_workflow\(.*\):" -p
```

### 2. Line-Level Evolution & Deep History (`git log -L`)
Trace how a specific block of code evolved over time, including all diffs that touched those lines:
```powershell
# Trace lines 15 to 45 in a file through history
git log -p -L 15,45:alos/memory/spec_rag.py
```

### 3. Line Attribution (`git blame`)
Identify the exact commit hash and author responsible for specific lines of code:
```powershell
# Blame lines 20 to 35
git blame -L 20,35 alos/memory/spec_rag.py
```

### 4. Inspecting Commit Rationale & Full Patches (`git show`)
Read the detailed commit message body and complete diff for a specific revision:
```powershell
git show <commit_hash>
```

### 5. Searching Commit Message Rationale (`git log --grep`)
Search commit messages (headers and bodies) for design decisions, issue references, or topics:
```powershell
git log --grep="ADR" --oneline
git log --grep="refactor" -n 10
```

### 6. Visualizing Branch History & Topography
Understand merge history, branch divergence, and feature timelines:
```powershell
git log --oneline --graph --decorate -n 20
```

---

## SYNTHESIS GUIDELINES FOR AGENTS

When analyzing Git history to answer user queries or inform implementation choices:
- **Quote Rationale**: Extract and synthesize key justifications from past commit message bodies when explaining legacy behavior.
- **Identify Historical Intent**: Distinguish between intentional architectural choices (supported by commit messages/ADRs) and temporary hotfixes or workarounds.
- **Contextualize Refactoring**: When refactoring code, preserve edge-case handling or constraints explicitly documented in historical commits.
