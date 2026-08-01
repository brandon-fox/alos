Feature: Dual-Loop Reasoning and Validation Self-Correction
  As Alex (User Persona)
  I want the Evaluator Node to critique planned action drafts against my rules
  So that invalid or conflicting plans automatically re-plan before execution.

  Scenario: Planner generates an invalid plan that violates user preferences
    Given the context preference "No meetings scheduled after 5:00 PM"
    When the Planner drafts a calendar event for "Team Sync at 5:30 PM"
    Then the Evaluator Node rejects the draft with validation error "Violates preference: No meetings scheduled after 5:00 PM"
    And ALOS routes back to Planner to self-correct the execution plan

  Scenario: Planner generates a valid plan that complies with preferences
    Given the context preference "No meetings scheduled after 5:00 PM"
    When the Planner drafts a calendar event for "Team Sync at 2:00 PM"
    Then the Evaluator Node approves the plan with status "VALID"
