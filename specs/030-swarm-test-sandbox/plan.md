# Architecture & Implementation Plan: Swarm Test Sandbox

**Feature Branch**: `feat/swarm-sandbox`
**Status**: Implemented

---

## Shape

```text
plan.json (drafts, and the mutants planned for each)
  |
  v
alos.swarm.sandbox            <- one container per draft, one more per mutant
  |  docker run --network none --read-only --cap-drop ALL --user 65534 ...
  v
container: python -m pytest /drafts/test_draft.py
  /repo     the repository, read-only bind mount
  /drafts   the draft, read-only bind mount
  /tmp      memory-backed, the only writable path
```

## Decisions

| Decision | Choice | Why |
| --- | --- | --- |
| Isolation | Container, repository mounted read-only, no network | The only local option where a bad draft cannot reach the home directory; the same runtime CI uses |
| Applying a mutant | Mount the mutated file read-only over the original | The repository is never written, so runs can overlap and a crash leaves nothing to clean up |
| What pytest sees | No config file, no cache, root at `/tmp` | The repository's own settings and conftest files must not change what a draft does |
| Sandbox failure | An exception and exit code 2, never a draft state | A broken runtime must not read as "all drafts failed" |
| Image | `Dockerfile.sandbox`, two stages | `base` has pytest and Hypothesis for standard-library code; the default stage adds the project's dependencies |
| Dependencies | Standard library only | Same rule as the dispatcher |

## Proof

Isolation is a claim about the runtime, so mocks cannot prove it. `tests/test_swarm_sandbox.py`
has container tests that run a hostile draft and compare a hash of the repository before and
after. They run in the `sandbox-isolation` job of `.github/workflows/sandbox-ci.yml` on every
pull request, with `ALOS_SANDBOX_REQUIRED=1` so a missing image fails the job instead of
skipping the tests.

## What gets hard later

- **Windows hosts.** Paths are passed to `--mount` as given. Docker Desktop accepts Windows
  paths; this is not yet tested there.
- **Readable by the container user.** The repository and the draft must be readable by uid
  65534. A git checkout is; a folder created with mode 700 is not.
- **Cost per mutant.** Each mutant is one container start, about a second. Hundreds of drafts
  with five mutants each is tens of minutes at four workers.
- **Timeouts as kills.** A mutant that makes the draft hang is recorded as `timeout` and does
  not count toward promotion.
