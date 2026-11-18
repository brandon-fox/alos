# spec: 028-enforce-fixed-action-hashes
Feature: Enforce Fixed GitHub Action Hashes
  As a maintainer of the ALOS CI pipeline
  I want every GitHub Action reference pinned to a full 40-character commit SHA with a version comment
  So that a repointed upstream tag cannot change what runs in CI

  # FR-001, SC-002 — enforced by tests/test_github_workflows.py::test_all_github_actions_use_fixed_hashes
  Scenario: Every action reference is a full commit SHA
    Given the workflow files under ".github/workflows/"
    When every "uses: <owner>/<repo>[/subpath]@<ref>" line is read
    Then each <ref> is a 40-character hexadecimal commit SHA
    And a local action reference starting with "./" is exempt

  # FR-003 — the gate fails on the first loose reference it finds
  Scenario: A tag or branch reference fails the gate
    Given a workflow step that uses "actions/checkout@v4"
    When the workflow test suite runs
    Then test_all_github_actions_use_fixed_hashes fails
    And the failure names the file, line and unpinned reference

  # FR-002 — enforced by tests/test_github_workflows.py::test_pinned_actions_carry_a_version_comment
  Scenario: Every pinned action carries a version comment
    Given a workflow step pinned to a commit SHA
    When the line is read
    Then it ends with a comment naming the release the SHA was taken from, such as "# v4.2.2"
