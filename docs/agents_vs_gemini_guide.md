# Architecture & Customization Guide: `.agents` vs `.gemini`

This document details how the Gemini / Antigravity AI Assistant discovers and loads customizations (Skills and Rules), the differences between the global `.gemini` home directory and workspace-local `.agents` directory, and operational best practices.

---

## 1. Overview & Scope

The assistant discovers customizations from two distinct root locations:

```
+---------------------------------------------------------------------------------+
|                               CUSTOMIZATION ROOTS                               |
|                                                                                 |
|  1. Global Customization Root:     C:\Users\<user>\.gemini\config\              |
|                                    (Applies globally across all projects)       |
|                                                                                 |
|  2. Workspace Customization Root:  <repo_root>/.agents/                          |
|                                    (Applies strictly to current repository)     |
+---------------------------------------------------------------------------------+
```

---

## 2. Comparison Matrix

| Dimension | **Global Root (`~/.gemini/`)** | **Workspace Root (`.agents/`)** |
| :--- | :--- | :--- |
| **Location** | `C:\Users\<user>\.gemini\config\` | `<repo_root>/.agents/` |
| **Scope** | **Global / User-wide** | **Project / Workspace-specific** |
| **Git Tracking** | **Untracked** (outside repo) | **Tracked** (checked into repository) |
| **Team Sharing** | Personal to your local machine | Shared across team members & CI |
| **Primary Use Cases** | Personal CLI habits, global tools, MCP credentials | Repo-level rules, `pyadr` enforcement, project specs |

---

## 3. Directory Structure & Elements

### A. Skills (`skills/<skill_name>/SKILL.md`)
Skills extend agent capabilities for specialized tasks. Each skill folder must contain a `SKILL.md` file with YAML frontmatter (`name`, `description`):

- **Workspace Local Skill**: `.agents/skills/pyadr-management/SKILL.md`
- **Global Skill**: `~/.gemini/config/skills/gcloud-auth-verification/SKILL.md`

### B. Rules (`AGENTS.md`)
Rules define style guidelines, architectural constraints, and operational boundaries:

- **Workspace Rules**: `.agents/AGENTS.md` (project-specific rules)
- **Global Rules**: `~/.gemini/config/AGENTS.md` (universal personal rules)

---

## 5. `AGENTS.md` vs `GEMINI.md` Files

### A. `AGENTS.md` (Rules File)
`AGENTS.md` is the standard markdown file used to specify persistent **behavioral rules, coding standards, and directives** for AI agents.

- **Workspace Level (`.agents/AGENTS.md`)**: Checked into Git. Contains repository-specific directives (e.g. mandatory `pyadr` usage, TDD requirements, file layout rules). Applied to any agent operating inside this workspace.
- **Global Level (`C:\Users\<user>\.gemini\config\AGENTS.md`)**: Untracked user file. Contains global personal preferences (e.g. shell preferences, output formatting rules) applied across all projects.

### B. `GEMINI.md` (Legacy / Alternate Configuration)
In earlier versions or specific Antigravity/Gemini SDK integrations, `GEMINI.md` served as a project-level instruction file (similar to `AGENTS.md` or `.clinerules`).

- **Current Best Practice**: Use `.agents/AGENTS.md` for project rules and `.agents/skills/<skill>/SKILL.md` for executable task skills. This aligns with the unified agent customization specification.
