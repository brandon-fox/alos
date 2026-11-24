# spec: 032-preemptible-compute-governor
Feature: CLI Workflow and Live RTX 5080 + Ollama Integration
  As the workstation owner
  I want the CLI commands (status, enqueue, tick, daemon) verified with both mocked and live calls
  So that every release is proven end-to-end before manual use

  @mocked
  Scenario: Mocked CLI end-to-end lifecycle across status, enqueue, tick, and standing daemon
    Given an isolated CLI SQLite database URL
    When I invoke the swarm queue CLI in mocked mode with "status"
    Then the CLI exits 0 with zero stderr warnings and JSON state "ARMED_IDLE"
    When I invoke the swarm queue CLI in mocked mode with "enqueue --id mock-cli-1 --tier fast_coder --prompt Summarize_hysteresis"
    Then the CLI exits 0 and reports job "mock-cli-1" in state "queued"
    When I invoke the swarm queue CLI in mocked mode with "tick"
    Then the CLI exits 0 and reports outcome "completed" for job "mock-cli-1"
    When I invoke the swarm queue CLI in mocked mode with "enqueue --id mock-cli-2 --tier fast_coder --prompt Check_daemon"
    And I invoke the swarm queue CLI in mocked mode with "daemon --max-ticks 2 --poll-s 0.02"
    Then the daemon CLI emits 3 JSON events "daemon_started", "daemon_tick", and "daemon_stopped"
    And the SQLite database records at least 1 capacity ledger entry

  @mocked
  Scenario: Mocked CLI tick gates execution cleanly when mocked sensor reports fullscreen gaming
    Given an isolated CLI SQLite database URL
    And I invoke the swarm queue CLI in mocked mode with "enqueue --id mock-gated-1 --tier fast_coder --prompt Blocked_by_game"
    When I invoke the swarm queue CLI in mocked gaming mode with "tick"
    Then the CLI exits 0 and reports outcome "gated" and state "USER_PREEMPTED"
    And job "mock-gated-1" remains queued in the SQLite database

  @live
  Scenario: Live CLI end-to-end workflow against real NVML telemetry and live Ollama model
    Given an isolated CLI SQLite database URL
    When I invoke the swarm queue CLI in live mode with "status"
    Then the CLI exits 0 with zero stderr warnings and positive total VRAM telemetry
    When I invoke the swarm queue CLI in live mode with "enqueue --id live-cli-1 --tier fast_coder --prompt Reply_with_the_single_word_READY"
    And I invoke the swarm queue CLI in live mode with "tick"
    Then the CLI exits 0 and reports outcome "completed" for job "live-cli-1"
    And job "live-cli-1" has a non-empty live model response in the SQLite database
    When I invoke the swarm queue CLI in live mode with "daemon --max-ticks 1 --poll-s 0.05"
    Then the daemon CLI emits 2 JSON events "daemon_started" and "daemon_stopped"

  @live
  Scenario: Live RTX 5080 warm epoch reuse followed by sub-2-second Direct3D game preemption
    Given a live HostGovernor and ComputeRuntimeLoop on port 11436
    When two "fast_coder" prompt jobs are enqueued and executed back to back
    Then both live jobs complete using the same warm Ollama server PID with >= 400 MiB managed VRAM
    When Direct3D fullscreen gaming is injected onto the live hardware sensor
    Then evaluating the live governor transitions to "USER_PREEMPTED" and evicts VRAM in under 2.0 seconds
    And live managed VRAM drops to 0 MiB with no running server PID

  @live
  Scenario: Live Ollama runner thermal cutoff and Schmitt-trigger hold against live hardware
    Given a live HostGovernor and ComputeRuntimeLoop on port 11436
    And one "fast_coder" prompt job is enqueued and executed to warm VRAM
    When an 84C GPU core temperature spike is injected onto the live hardware sensor
    Then evaluating the live governor transitions to "COOLING_CUTOFF" and evicts VRAM in under 2.0 seconds
    When GPU temperature cools partway to 77C and another live job is enqueued
    Then running one live loop tick returns outcome "gated" without respawning Ollama
