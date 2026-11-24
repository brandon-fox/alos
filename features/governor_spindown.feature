# spec: 032-preemptible-compute-governor
@mocked
Feature: Host Governor Preemption, Orphan Eviction, and Thermal Hysteresis
  As a developer running ALOS on a single-GPU gaming workstation
  I want local models and worker containers to yield immediately on gaming or heat
  So that desktop responsiveness and hardware thermals are never compromised

  Scenario: T1 - Direct3D fullscreen game launch preempts active work and pauses containers
    Given a mocked compute governor in "WARM_ACTIVE" with container "devcontainer-alos"
    When host telemetry reports Direct3D fullscreen gaming
    Then evaluating the governor with queued work transitions to "USER_PREEMPTED"
    And the cancellation event is signaled
    And container "devcontainer-alos" is paused via docker
    And the model spinner evicts VRAM once

  Scenario: T1 - Foreign VRAM spike and blocked process preempt while ignoring WDDM sentinels
    Given a mocked compute governor in "WARM_ACTIVE" with container "devcontainer-alos"
    When NVML reports WDDM sentinel process memory with 2800 MiB total used VRAM
    Then evaluating the governor with queued work stays in "WARM_ACTIVE"
    When host telemetry reports 8500 MiB used VRAM with 3000 MiB managed VRAM
    Then evaluating the governor with queued work transitions to "USER_PREEMPTED"
    When foreign VRAM clears to 2500 MiB and idle hits 320s but blocked process "Game.exe" runs
    Then evaluating the governor with queued work stays in "USER_PREEMPTED"

  Scenario: T1 - Preemption holds during active mouse input and recovers after full idle window
    Given a mocked compute governor in "WARM_ACTIVE" with container "devcontainer-alos"
    When host telemetry reports Direct3D fullscreen gaming
    And evaluating the governor with queued work transitions to "USER_PREEMPTED"
    When gaming stops with 2600 MiB used VRAM and 45s user idle
    Then evaluating the governor with queued work stays in "USER_PREEMPTED"
    When user idle reaches 310s with 2600 MiB used VRAM
    Then evaluating the governor with queued work transitions to "ARMED_IDLE"
    And container "devcontainer-alos" is unpaused via docker
    And the cancellation event is cleared

  Scenario: T2 - Hung Ollama server process tree is forcibly killed under 2 seconds
    Given a live dummy child process attached to a ModelSpinner on port 11499
    When the ModelSpinner executes evict_all
    Then the eviction completes in under 2.0 seconds with tree_killed true
    And the dummy child process is terminated

  Scenario: T2 - Adaptive CUDA OOM slot backoff halves parallel slots until model warms
    Given a ModelSpinner configured with 8 slots that hits CUDA OOM above 2 slots
    When ensure_tier is called for "fast_coder"
    Then the spinner backs off slots from 8 to 4 to 2 and succeeds at 2 slots

  Scenario: T3 - Thermal ramp enforces Schmitt-trigger hysteresis and resets dwell on bounce
    Given a mocked compute governor in "WARM_ACTIVE" with container "devcontainer-alos"
    When host temperatures reach GPU 76C, VRAM 80C, CPU 70C
    Then evaluating the governor with queued work transitions to "THROTTLED"
    When host temperatures reach GPU 78C, VRAM 95C, CPU 72C
    Then evaluating the governor with queued work transitions to "COOLING_CUTOFF"
    When clock advances 60s and temperatures cool partway to GPU 64C, VRAM 80C, CPU 65C
    Then evaluating the governor with queued work stays in "COOLING_CUTOFF"
    When temperatures drop below recovery floor to GPU 54C, VRAM 70C, CPU 55C
    Then evaluating the governor without work stays in "COOLING_CUTOFF"
    When clock advances 100s and GPU briefly spikes to 62C then returns to 54C
    Then evaluating the governor without work resets the recovery dwell timer
    When clock advances 185s at GPU 54C, VRAM 70C, CPU 55C
    Then evaluating the governor without work transitions to "ARMED_IDLE"

  Scenario: Throttled state blocks cold tier swaps and warm linger evicts after 600s
    Given a mocked runtime loop with active tier "reasoner"
    When host telemetry enters light desktop input throttle with 10s idle
    And a "fast_coder" job is enqueued while "reasoner" is warm
    Then running one loop tick returns outcome "throttled_wait" without swapping tiers
    When a "reasoner" job is enqueued while "reasoner" is warm
    Then running one loop tick returns outcome "completed" on "reasoner"
    When user idle returns to 600s and clock advances 605s with an empty queue
    Then evaluating the governor without work evicts VRAM and transitions to "ARMED_IDLE"
