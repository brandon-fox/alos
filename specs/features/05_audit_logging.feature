Feature: Immutable System Audit Logging
  As Alex (User Persona)
  I want all state transitions, tool calls, and self-correction loops written to an append-only JSONL log
  So that I have full transparency and zero data corruption across restarts.

  Scenario: Audit logger appends state transitions to audit log file
    Given an initialized System Audit Logger target file "logs/system_audit.jsonl"
    When ALOS completes execution step "Context Assembly" with status "SUCCESS"
    And ALOS completes execution step "Evaluator Check" with status "REJECTED" and reason "Preference Violation"
    Then "logs/system_audit.jsonl" contains valid JSONL records for each step
    And every log entry includes timestamp, step name, and status
