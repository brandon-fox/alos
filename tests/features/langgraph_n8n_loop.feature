Feature: LangGraph Autonomous Self-Reflection Loop for n8n

  Scenario: n8n execution succeeds on initial attempt
    Given an n8n polling task with valid payload
    When the LangGraph self-reflection loop executes
    Then the task status is "success"
    And attempt count is 1

  Scenario: n8n execution fails initial evaluation and self-corrects
    Given an n8n polling task with initial missing required parameter "api_key"
    When the LangGraph self-reflection loop executes
    Then the evaluation detects missing parameter "api_key"
    And the payload is refined with parameter "api_key"
    And the loop retries execution
    And the final task status is "success"
    And attempt count is 2

  Scenario: n8n execution exceeds maximum retry attempts
    Given an n8n polling task that continuously fails validation
    When the LangGraph self-reflection loop executes with max attempts set to 2
    Then the loop terminates with status "failed_max_retries"
    And attempt count is 2
