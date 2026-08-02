Feature: SpecKit Lifecycle and Archiving Integration
  As a developer
  I want to track spec lifecycle states and archive completed features
  So that repository specs remain well-organized, versioned, and extensible

  Scenario: Transitioning a spec through valid lifecycle states
    Given a feature spec "027-speckit-lifecycle-archiving" in state "draft"
    When I transition the spec state to "in_progress"
    Then the current state of the spec should be "in_progress"
    And the lifecycle transition history should record the change

  Scenario: Rejecting invalid spec state transition
    Given a feature spec "027-speckit-lifecycle-archiving" in state "draft"
    When I attempt an invalid transition directly to "archived"
    Then an InvalidStateTransitionError should be raised
    And the spec state should remain "draft"

  Scenario: Archiving a completed feature spec
    Given a feature spec "027-speckit-lifecycle-archiving" in state "completed"
    When I run the archive operation for feature "027-speckit-lifecycle-archiving"
    Then the feature folder should be moved to "specs/archive/027-speckit-lifecycle-archiving"
    And "specs/archive/archive-index.json" should contain an entry for "027-speckit-lifecycle-archiving"

  Scenario: Restoring an archived feature spec
    Given an archived feature "027-speckit-lifecycle-archiving" in "specs/archive/"
    When I run the restore operation for feature "027-speckit-lifecycle-archiving"
    Then the feature folder should be restored to "specs/027-speckit-lifecycle-archiving"
    And the entry in "specs/archive/archive-index.json" should be removed

  Scenario: Plugin hook execution on lifecycle transition
    Given a registered plugin hook for "on_lifecycle_transition"
    When a spec state transition occurs
    Then the plugin hook should be invoked with transition details
