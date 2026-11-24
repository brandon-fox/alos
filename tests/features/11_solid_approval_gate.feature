# spec: 036-hexagonal-twelve-factor-refactor
Feature: SOLID Dual-Loop Orchestrator and HIGH-Risk Human Approval Gate
  @mocked
  Scenario: HIGH-risk blocks on HumanApprovalGatePort while LOW-risk runs autonomously
    Given a mocked DualLoopOrchestrator with mocked ports and HIGH-risk approval gate
    When high-risk email actions and low-risk web search actions execute
    Then unapproved HIGH-risk returns PENDING_APPROVAL while approved and LOW-risk succeed
  @live
  Scenario: Strangler-Fig ALOSStateGraph preserves real vault self-correction and approval gating
    Given a live temporary vault with ALOSStateGraph and real audit and decision loggers
    When a meeting query and an unapproved high-risk email query run end-to-end
    Then the meeting self-corrects cleanly on disk while the email halts at PENDING_APPROVAL
