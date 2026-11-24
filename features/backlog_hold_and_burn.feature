# spec: 037-backlog-staging-and-burn
@mocked
Feature: Active-Use Queue Hold Latch and Deliverable Burn CLI
  As the workstation owner
  I want staged backlogs held while I am actively using the machine and burned into Markdown artifacts when resumed
  So that queue execution never disrupts active work and always produces concrete outputs

  Scenario: Pause with idle gate blocks tick while active and burn drains after resume
    Given an isolated Spec 037 ALOS_HOME
    When I run the Spec 037 queue CLI in active-user mode with "enqueue --id bdd-burn-1 --repo brandon-fox/alos --workflow issue_plan --tier fast_coder --requires-merge --prompt Plan_PR_12_adapters"
    And I run the Spec 037 queue CLI in active-user mode with "pause --arm-after-idle 300"
    And I run the Spec 037 queue CLI in active-user mode with "tick"
    Then the Spec 037 CLI reports outcome "held_user_active"
    When I run the Spec 037 queue CLI in active-user mode with "resume"
    And I run the Spec 037 queue CLI in active-user mode with "burn --max-jobs 2"
    Then the Spec 037 burn report shows 1 completed job and creates the Markdown deliverable
    When I run the Spec 037 queue CLI in active-user mode with "review --repo brandon-fox/alos --approve-all"
    Then the Spec 037 review report updates 1 job to "succeeded"

  Scenario: Multi-repository backlog stages over two hours of work while holding execution
    Given an isolated Spec 037 ALOS_HOME
    When I run the Spec 037 queue CLI in active-user mode with "backlog stage --target-minutes 150 --arm-after-idle 300"
    Then the Spec 037 backlog stage report stages at least 25 jobs across 4 repositories
    When I run the Spec 037 queue CLI in active-user mode with "tick"
    Then the Spec 037 CLI reports outcome "held_user_active"
