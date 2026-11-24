Feature: Automatic Signed PR Rebase and Universal Auto-Merge
  As an ALOS maintainer
  I want all pull requests to automatically enable auto-merge and stay rebased onto main with signed commits
  So that First-ADE Axiom A7 never fails on rebase, merge, or bot commits

  @mocked
  Scenario: Universal auto-merge enables auto-merge on all non-hold PRs including drafts and bots
    Given the GitHub workflow ".github/workflows/auto-merge.yml"
    Then it marks non-hold draft pull requests ready for review before enabling auto-merge
    And it enables squash auto-merge for human, Dependabot, and bot pull requests
    And it skips pull requests labeled "wip" or "do-not-merge"

  @mocked
  Scenario: Signed rebase rewrites behind and unsigned PR commits with SSH signatures
    Given a bare remote repository with main advanced ahead of a feature branch
    And the feature branch contains an unsigned commit
    When signed_pr_rebase executes in single mode with an ephemeral SSH signing key
    Then the feature branch is rebased onto origin main
    And every commit between origin main and HEAD carries a gpgsig header

  @mocked
  Scenario: Rebase conflict aborts cleanly without corrupting the PR branch
    Given a bare remote repository where main and the feature branch modify the same line
    When signed_pr_rebase executes in single mode with an ephemeral SSH signing key
    Then the rebase reports status "conflict"
    And the feature branch tip remains unchanged without leftover rebase state

  @mocked
  Scenario: Queue mode skips conflicting PRs and rebases the next eligible PR
    Given open pull requests where the oldest behind PR has a merge conflict and the second behind PR is clean
    When signed_pr_rebase selects and rebases the next queue candidate
    Then the conflicting PR is skipped and the clean PR is rebased with signed commits
