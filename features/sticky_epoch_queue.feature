# spec: 032-preemptible-compute-governor
@mocked
Feature: Sticky Model-Epoch Queue, Resumable Checkpoints, and Capacity Caps
  As a local orchestration engine operating on 16 GB of single-GPU VRAM
  I want queued jobs batched by warm model tier and checkpointed across preemptions
  So that weight-swap thrashing and wasted tokens are eliminated

  Scenario: Sticky model-epoch affinity drains matching tier before switching
    Given an isolated SQLite sticky epoch queue
    And jobs enqueued in order: "c1:fast_coder:50", "r1:reasoner:50", "c2:fast_coder:50", "r2:reasoner:50"
    When a worker leases and completes all 4 jobs starting with active tier "reasoner"
    Then the leased job order is "r1,r2,c1,c2"

  Scenario: Epoch duration cap prevents starvation of higher-priority waiting tiers
    Given an isolated SQLite sticky epoch queue with 600s max epoch
    And jobs enqueued in order: "c1:fast_coder:65", "r1:reasoner:50", "r2:reasoner:50"
    When a worker leases one job with active tier "reasoner"
    Then the leased job is "r1"
    When the monotonic clock advances 610s past the epoch cap
    And a worker leases the next job with active tier "reasoner"
    Then the leased job is "c1"

  Scenario: Preempted job preserves LangGraph checkpoint and resumes without burning retries
    Given an isolated SQLite sticky epoch queue
    And jobs enqueued in order: "j1:fast_coder:50", "j2:fast_coder:55"
    When a worker leases the top job and preempts it at checkpoint "lg-thread-99:node-2"
    Then job "j2" is stored in state "preempted" with 1 attempt and checkpoint "lg-thread-99:node-2"
    When a worker leases the next job with active tier "fast_coder"
    Then the resumed job is "j2" with 1 attempt and checkpoint "lg-thread-99:node-2"

  Scenario: Failure retry budget re-queues once and escalates at max_attempts
    Given an isolated SQLite sticky epoch queue
    And a job "flaky-1" on tier "fast_coder" with max_attempts 2
    When "flaky-1" is leased and fails with "schema mismatch"
    Then job "flaky-1" returns to state "queued" with 1 attempt
    When "flaky-1" is leased again and fails with "schema mismatch"
    Then job "flaky-1" moves to state "escalated" with 2 attempts

  Scenario: Per-repository 3-open-PR merge cap skips 4th merge job while running no-merge work
    Given an isolated SQLite sticky epoch queue with max 3 open merge jobs
    And 3 completed merge jobs are pending review on repository "alos"
    When merge job "pr-4" and no-merge job "index-1" on "alos" and merge job "other-pr-1" on "nectR" are enqueued
    Then leasing two jobs yields "index-1" and "other-pr-1" while leaving "pr-4" queued

  Scenario: Expired leases reclaim automatically and cloud-eligible jobs promote to overflow
    Given an isolated SQLite sticky epoch queue with 60s lease TTL and 300s overflow wait
    And job "lease-timeout" with priority 60 and cloud-overflow job "cloud-wait" with priority 50
    When "lease-timeout" is leased and wall clock advances 350s without completion
    And a worker leases the next available job
    Then "lease-timeout" is reclaimed and re-leased while "cloud-wait" moves to state "overflow"
