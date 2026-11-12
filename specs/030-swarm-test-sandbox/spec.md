# Feature Specification: Swarm Test Sandbox

**Feature Branch**: `feat/swarm-sandbox`
**Created**: 2026-11-10
**Status**: Draft (implemented and proven against real containers; not yet run on a night's drafts)

---

## Intent

A draft test is code written by a local model. It may patch the environment, start
subprocesses, delete files or open sockets, by mistake or because its input told it to. So a
draft is never run on the host and never run where it can change the code it tests.

The sandbox answers two questions about one draft, and nothing else:

1. **Does it pass against the code as it is?** If not, it is not a test of this code.
2. **Can it fail?** A draft that passes is run again against small deliberate breakages of
   the code (mutants). If no mutant makes it fail, it proves nothing and is not promoted.

The dispatcher ([spec 029](../029-local-swarm-dispatcher/spec.md)) produces drafts and mutant
plans. This feature is the gate between a draft and a pull request.

## Contracts

**Plan** (`plan.json`, written by whatever collected the drafts):

```json
{
  "image": "alos-sandbox:latest",
  "timeout_s": 120,
  "jobs": [
    { "id": "clamp-01",
      "repo": "/abs/path/to/clone",
      "test": "/abs/path/to/draft_test.py",
      "mutants": [
        { "file": "pkg/calc.py", "line": "return min(value, high)", "mutated": "return value" }
      ] }
  ]
}
```

A job id matches `^[A-Za-z0-9._-]+$`. A mutant names a file inside the repository, one source
line copied from it, and the line that replaces it.

**Results** (`sandbox-results.json`):

```json
{ "image": "alos-sandbox:latest", "counts": { "passed": 1 }, "promoted": 1,
  "results": [
    { "id": "clamp-01", "state": "passed", "passed": 2, "failed": 0, "seconds": 1.4,
      "mutants": [ { "file": "pkg/calc.py", "line": "...", "state": "killed" } ],
      "promote": true } ] }
```

Draft `state` is `passed`, `failed`, `error` (pytest could not collect or run it), `empty` (no
test ran) or `timeout`. Mutant `state` is `killed`, `survived`, `not_found` (the line is not in
the file, or the file is outside the repository), `invalid` (the mutated file does not compile)
or `timeout`. `promote` is true only when the draft passed and at least one mutant was killed.

A failure of the sandbox itself (no runtime, no image, a runtime error) is never recorded as a
draft state. It stops the plan with exit code 2.

## Scenarios

```gherkin
Feature: Isolation
  Scenario: A draft cannot change the repository
    Given a draft that deletes or overwrites files under the repository
    When it runs in the sandbox
    Then every attempt fails inside the container
    And the repository on the host is byte-for-byte unchanged

  Scenario: A draft cannot reach the network
    Given a draft that opens a socket
    When it runs in the sandbox
    Then the connection fails because the container has no network

  Scenario: A draft has nowhere to persist anything
    Given any draft
    When it runs
    Then the container root is read-only
    And the only writable place is a memory-backed /tmp that is discarded with the container

  Scenario: A draft runs without privilege
    Given any draft
    When it runs
    Then it runs as an unprivileged user with no capabilities and no way to gain them
    And it is limited in memory, CPU and process count

Feature: Run a draft
  Scenario: The draft is the only thing collected
    Given a repository with its own pytest configuration and conftest files
    When a draft runs
    Then pytest is started with no configuration file and no cache
    And only the draft's tests are collected

  Scenario: A draft never finishes
    Given a draft that loops forever
    When the wall clock runs out
    Then the container is killed and removed
    And the draft is recorded as "timeout"

  Scenario: The sandbox cannot run
    Given the container runtime or the image is missing
    When a plan is started
    Then no draft is run and no draft is blamed
    And the command exits with code 2 and says what is missing

Feature: A kept test must be able to fail
  Scenario: A mutant is applied without touching the source
    Given a passing draft and a planned mutant
    When the mutant is tried
    Then the mutated file is mounted read-only over the original inside the container
    And the file in the repository is not modified

  Scenario: Promotion
    Given a passing draft
    When at least one mutant makes it fail
    Then the draft is marked for promotion

  Scenario: A test that cannot fail
    Given a passing draft
    When every mutant survives, or no mutant could be applied
    Then the draft is not promoted

  Scenario: A mutant from a model is not trusted
    Given a mutant that names a file outside the repository, a line that is not in the file,
      or a replacement that does not compile
    When it is prepared
    Then it is recorded as "not_found" or "invalid" and no container is started for it
```

## Out of scope

- Collecting a night's drafts into a plan, and opening pull requests for promoted drafts. Both
  belong to spec 029 stage 2.
- Tests in other languages. The sandbox runs pytest.
- Defending against a container escape in the runtime itself. The sandbox relies on the
  runtime's isolation and removes what a draft does not need: network, capabilities, a writable
  root and privilege.

## Kill criteria

Judged by the maintainer, not measured by a job.

- Fewer than half of the large model's unit-test drafts pass their first sandbox run: stop
  drafting tests per function.
- The reviewing model's "keep" verdict agrees with a sandbox pass less than 70% of the time:
  drop the review stage.
