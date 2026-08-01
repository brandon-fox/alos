Feature: Model Context Protocol (MCP) Tool Integration Layer
  As Alex (User Persona)
  I want standardized MCP client gateways for Google Workspace, Todoist, and Vault
  So that external services interact reliably via typed Pydantic payloads.

  Scenario: Create a Todoist task via MCP Gateway
    Given an MCP Gateway connected to Todoist
    When an authorized action "TodoistTaskCreate" with title "Schedule quarterly review" and due_date "2026-08-05" is dispatched
    Then the MCP Gateway translates payload into standard tool call
    And the task is successfully created on Todoist

  Scenario: Query Google Calendar events via MCP Gateway
    Given an MCP Gateway connected to Google Workspace
    When ALOS requests calendar events for "2026-08-01"
    Then the MCP Gateway queries Google Calendar MCP server
    And returns structured calendar events matching the date
