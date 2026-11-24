# spec: 034-portable-production-runtime
# spec: 034-portable-production-runtime
Feature: Portable Install and Hardened Container Production Runtime
  As an operator deploying ALOS across workstations or containers
  I want relocatable bootstrap, health probes, PID locks, wheel installs, and non-root containers
  So that ALOS starts, monitors, and stops reliably without a source checkout

  @mocked
  Scenario: Portable bootstrap seeds bundled vault templates and preserves user customizations
    Given an empty portable ALOS_HOME directory
    When I run the unified alos CLI in mocked mode with "bootstrap"
    Then ALOS_HOME contains seeded vault templates, alos.env, and an initialized SQLite database
    When I customize USER_PROFILE.md inside ALOS_HOME and re-run "bootstrap"
    Then USER_PROFILE.md retains my customization with zero overwritten files

  @mocked
  Scenario: Single-instance daemon lock rejects duplicate daemons and reclaims dead PID locks
    Given a bootstrapped portable ALOS_HOME directory
    When an active SingleInstanceLock is held on ALOS_HOME
    And I run the unified alos CLI in mocked mode with "daemon --max-ticks 1 --poll-s 0.02"
    Then the unified CLI exits with code 3 and reports event "daemon_locked"
    When the active lock is replaced by a stale dead-PID lockfile
    And I run the unified alos CLI in mocked mode with "daemon --max-ticks 1 --poll-s 0.02"
    Then the unified CLI exits with code 0 and reclaims the stale lock cleanly

  @mocked
  Scenario: Daemon writes atomic health.json heartbeats and exposes capacity history via ledger
    Given a bootstrapped portable ALOS_HOME directory
    When I run the unified alos CLI in mocked mode with "enqueue --id port-m1 --tier fast_coder --prompt Check_health"
    And I run the unified alos CLI in mocked mode with "daemon --max-ticks 1 --poll-s 0.02"
    Then ALOS_HOME health.json exists with status "stopped"
    When I run the unified alos CLI in mocked mode with "ledger --limit 5"
    Then the ledger JSON output contains at least 1 entry

  @mocked
  Scenario: Readiness doctor passes in mocked mode and fails when required Ollama is unreachable
    Given a bootstrapped portable ALOS_HOME directory
    When I run the unified alos CLI in mocked mode with "doctor --json"
    Then the doctor JSON reports healthy true with exit code 0
    When run_doctor is invoked requiring an unreachable Ollama port
    Then the doctor report marks healthy false

  @live
  Scenario: Built wheel installs into an external prefix and runs end-to-end against live Ollama
    Given a built ALOS wheel installed into an isolated external runtime prefix
    When the installed alos binary runs "bootstrap" and "doctor --json --require-ollama" from an external working directory
    Then both installed binary commands exit 0 with healthy live GPU and Ollama checks
    When the installed alos binary enqueues job "wheel-live-01" and runs "tick" from the external working directory
    Then the installed binary completes "wheel-live-01" against live Ollama using only the external ALOS_HOME

  @live @docker_live @docker_only
  Scenario: Production Dockerfile builds non-root image and passes container bootstrap and doctor
    Given docker compose configuration with profile "alos" validates cleanly
    When the production Dockerfile is built as image "alos:bdd-prod"
    Then the container image runs as non-root UID "10001"
    And running "bootstrap", "doctor --json", and mocked "daemon --max-ticks 1 --poll-s 0.02" inside the container all exit 0
