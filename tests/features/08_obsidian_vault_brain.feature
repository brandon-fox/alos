Feature: Obsidian Vault Brain Integration
  As an ALOS autonomous agent
  I want to parse Obsidian vault notes, frontmatter tags, WikiLinks, and build a bi-directional knowledge graph
  So that my long-term memory, daily journal, user profile, and preferences remain local and graph-connected.

  Scenario: Parse YAML frontmatter and WikiLinks from Obsidian notes
    Given an Obsidian vault directory with a note containing frontmatter and [[WikiLinks]]
    When ObsidianVaultParser processes the note
    Then frontmatter tags, custom properties, and WikiLinks must be extracted cleanly

  Scenario: Build bi-directional Knowledge Graph and neighborhood traversal
    Given an Obsidian vault with linked notes A -> B and B -> C
    When ObsidianGraphEngine builds the graph
    Then neighborhood resolution for A at depth 2 must return notes A, B, and C

  Scenario: Synthesize Daily Notes and Memory Notes
    Given a daily journal entry request for ALOS
    When ObsidianBrainSynthesizer creates or appends a daily note
    Then the note must be written under vault/Daily Notes/ with valid frontmatter and content
