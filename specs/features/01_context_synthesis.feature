Feature: Context Synthesis & Local Vault RAG Retrieval
  As Alex (User Persona)
  I want ALOS to index my local Markdown vault and retrieve relevant contextual rules
  So that every action planned by ALOS reflects my profile, preferences, and past corrections.

  Scenario: Assemble context from Markdown vault files
    Given a local vault containing "USER_PROFILE.md", "PREFERENCES.md", and "CORRECTION_LEDGER.md"
    And "PREFERENCES.md" contains rule "No meetings scheduled after 5:00 PM"
    And "CORRECTION_LEDGER.md" contains entry "Never book flights without checking Delta options first"
    When Alex submits a task request "Plan my trip to San Francisco and update my schedule"
    Then ALOS Context Assembler synthesizes a context payload
    And the context payload includes the preference "No meetings scheduled after 5:00 PM"
    And the context payload includes the past correction "Never book flights without checking Delta options first"
