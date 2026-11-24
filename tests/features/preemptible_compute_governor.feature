# spec: 032-preemptible-compute-governor
Feature: Preemptible Host Governor and Sticky Epoch Queue

  Scenario: Game launch preempts active model and pauses containers
    Given a warm local compute governor with registered container "alos-dev-1"
    When Direct3D fullscreen gaming activity is detected
    Then the governor state transitions to "USER_PREEMPTED"
    And worker container "alos-dev-1" is paused
    And the active model tier is evicted from VRAM

  Scenario: Thermal ramp enforces Schmitt-trigger hysteresis without bounce
    Given a warm local compute governor with registered container "alos-dev-1"
    When GPU core temperature rises to 76C and then 83C
    Then the governor state transitions to "COOLING_CUTOFF"
    When GPU core temperature drops slightly to 78C
    Then the governor state remains "COOLING_CUTOFF"
    When GPU core temperature holds at 55C across the recovery dwell window
    Then the governor state recovers to "ARMED_IDLE"

  Scenario: Sticky epoch queue drains warm model tier before swapping
    Given a sticky epoch queue with alternating "fast_coder" and "reasoner" jobs
    When a worker pulls jobs while "reasoner" is the active warm tier
    Then all "reasoner" jobs lease before any "fast_coder" job
