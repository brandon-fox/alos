Feature: Local Spec and Vault RAG Knowledge Base Engine
  As an ALOS autonomous agent
  I want a local-first markdown RAG indexer
  So that I can search specs, references, constitution constraints, and vault notes with section header precision.

  Scenario: Index markdown sections and header weights
    Given repository root containing specs/, vault/, and constitution files
    When SpecRAGIndexer builds index
    Then markdown sections delineated by headers must be searchable with header weighting

  Scenario: Filter RAG search results by source type
    Given indexed documents across spec, vault, and constitution sources
    When SpecRAGIndexer performs search with source_filter
    Then only chunks matching the specified source_type must be returned
