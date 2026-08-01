Feature: Alex Persona Integration & End-to-End Memory Behavior
  As tech executive persona Alex
  I want ALOS to honor privacy constraints, enforce Safety Matrix risk gates, remember past corrections, and traverse graph memory
  So that administrative life tasks are automated safely without privacy leaks or repeated errors.

  Scenario: Honor local-first privacy constraint for executive profile
    Given user profile Alex with vault storage on local disk
    When ALOS evaluates user query and context payload
    Then context evaluation must execute strictly locally without third-party API exposure

  Scenario: Self-correct based on past ledger entries and Obsidian graph memory
    Given CORRECTION_LEDGER note specifying "Never book flights without checking Delta options first"
    And linked memory note [[Delta Flight Preference]]
    When Planner generates a flight booking draft
    Then Evaluator must verify compliance against graph memory and reject non-compliant plans
