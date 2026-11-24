# spec: 037-backlog-staging-and-burn
Feature: Active-Use Queue Hold Latch, Missing-Tag Fallback, and Artifact Burn
  As a workstation owner staging multi-hour backlogs while actively coding
  I want staged tasks held at zero VRAM while active and burned into reviewable Markdown and worktrees once idle
  So that desktop responsiveness is preserved and every completed task leaves a concrete deliverable

  Scenario: Manual and idle-gated hold latches block execution while active and auto-arm on idle
    Given an isolated ALOS_HOME queue with a staged "spec_audit" job
    When a 300-second idle-gate hold latch is engaged while user idle is 20 seconds
    Then running a queue tick returns "held_user_active" with zero model loads
    When user idle reaches 320 seconds
    Then running a queue tick clears the hold latch and completes the job

  Scenario: Missing primary Ollama tier tag steps down to installed fallback and writes deliverables
    Given a ModelSpinner whose primary "reasoner" tag returns HTTP 404 while fallback is installed
    When the runtime loop executes a "task_patch" job with optional git worktree enabled
    Then the spinner warms the fallback model and writes the Markdown deliverable and burn digest
    And an isolated git worktree branch "alos-burn/" is created without modifying main
