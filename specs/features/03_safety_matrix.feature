Feature: Safety Matrix & Action Risk Tier Gating
  As Alex (User Persona)
  I want low and medium risk actions to run automatically, but high risk actions to require explicit user approval
  So that irreversible external mutations never execute without my consent.

  Scenario: Low risk action executes automatically
    Given a planned action "Search web for top rated driveway contractors"
    When ALOS evaluates action risk level
    Then the risk tier is categorized as "LOW"
    And ALOS executes the action without requiring real-time user confirmation

  Scenario: Medium risk action executes automatically with schema check
    Given a planned action "Create Todoist task: Buy driveway sealant"
    When ALOS evaluates action risk level
    Then the risk tier is categorized as "MEDIUM"
    And ALOS validates Pydantic schema and executes automatically

  Scenario: High risk action prompts for user approval
    Given a planned action "Send external email to contractor@example.com"
    When ALOS evaluates action risk level
    Then the risk tier is categorized as "HIGH"
    And ALOS intercepts the action and requires explicit human approval before execution
