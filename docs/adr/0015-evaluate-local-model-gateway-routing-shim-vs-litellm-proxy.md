# Evaluate Local Model Gateway Routing Shim vs LiteLLM Proxy

* Status: proposed
* Deciders: Brandon Fox
* Date: 2026-11-23

Technical Story: `specs/031-preemptible-compute-governor/spec.md` (Slice 4 Open Architectural Decision)

## Context and Problem Statement

Orchestration frameworks (LangGraph in `alos`, `first-ade`, external OpenAI-compatible coding agents, and devcontainer tools) need a unified `/v1/chat/completions` endpoint that maps semantic capability tiers (`local/fast-coder`, `local/reasoner`, `local/architect`, and budget-capped `cloud/escalate`) onto the active Ollama epoch server (`:11435` / `:11434`) or cloud fallback. Should ALOS embed a lightweight Python `/v1/chat/completions` routing shim directly inside the `HostGovernor` process, or run a standalone LiteLLM Proxy container in Docker Compose?

## Decision Drivers

* **Preemption Coupling**: When the `HostGovernor` transitions to `USER_PREEMPTED` or `COOLING_CUTOFF`, in-flight `/v1/chat/completions` streams must abort within `< 250ms` and return a deterministic `503 Service Unavailable (Preempted)` code so LangGraph workers checkpoint rather than count the failure against model retry budgets.
* **Epoch Awareness**: Requests targeting a cold `model_tier` while another tier is mid-epoch must either queue cleanly, yield back to the epoch scheduler, or reject fast without silently forcing Ollama to swap weights in 16 GB VRAM.
* **Operational Footprint ("Goal is to Start")**: Minimizing container sprawl, dependency weight, startup latency, and configuration drift on a single workstation.
* **Protocol Compatibility**: Supporting OpenAI Chat Completions (`stream`, `response_format` / structured JSON schema, `tools`, token usage accounting) across LangGraph `ChatOpenAI`, Instructor, and cloud overflow providers (Anthropic Claude, Google Gemini).

## Considered Options

* Option A: Built-in lightweight Python `/v1/chat/completions` HTTP/ASGI shim owned directly by `HostGovernor`
* Option B: Standalone LiteLLM Proxy service inside `docker-compose.yml` routing to `host.docker.internal` Ollama ports and cloud APIs

## Decision Outcome

Chosen option: "Undecided (Deferred to Slice 4 Gateway Benchmark)", because Slices 1 and 2 (`HostGovernor`, `ModelSpinner`, and `StickyEpochQueue`) operate directly against `ModelSpinner` without locking in the external HTTP proxy surface; both candidates are recorded below with concrete evaluation criteria before Slice 4 implementation.

### Evaluation Gate to Close This ADR

* Measure cold-start memory overhead, streaming abort latency under `T1` preemption (`< 250ms` target), and LangGraph structured-output + tool-calling compatibility across `qwen2.5-coder:7b-instruct`, `gemma4:12b`, and `qwen3-coder:30b`.

## Pros and Cons of the Options

### Option A: Built-in lightweight Python `/v1/chat/completions` HTTP/ASGI shim owned directly by `HostGovernor`

Direct in-process OpenAI-compatible endpoint (`127.0.0.1:4000/v1/chat/completions` and `/v1/embeddings`) sharing memory with `HostGovernor` and `ModelSpinner`.

* Good, because `HostGovernor` holds direct references to every active HTTP stream and `asyncio.Event`, aborting requests in `< 50ms` on gaming/thermal preemption and returning structured `retry_after` / `preempted` metadata.
* Good, because it has direct zero-IPC visibility into `ModelSpinner.active_tier`, preventing uncoordinated weight swaps when a caller asks for a non-active model tier.
* Good, because it adds zero Docker containers, zero extra database schemas, and starts in `< 100ms` alongside `python -m alos.swarm.governor`.
* Bad, because ALOS must maintain translation glue for cloud escalation providers (Claude Messages API / Gemini API) if `ChatAnthropic` / `ChatGoogleGenerativeAI` are not invoked directly by LangGraph.
* Bad, because edge-case OpenAI SDK features (complex streaming `tool_calls` chunk deltas) must be tested and maintained in-house.

### Option B: Standalone LiteLLM Proxy service inside `docker-compose.yml` routing to `host.docker.internal` Ollama ports and cloud APIs

Config-driven `ghcr.io/berriai/litellm` container listening on `:4000` configured via `litellm_config.yaml` with model aliases, budgets, and fallbacks.

* Good, because OpenAI-to-Ollama, Anthropic Claude, and Google Gemini protocol translation (including streaming tool calls, structured schemas, and spend caps) works out of the box.
* Good, because built-in token/cost tracking and fallback chains require YAML configuration rather than custom adapter code.
* Bad, because LiteLLM has no native awareness of `HostGovernor` thermal/gaming states or single-GPU `ModelSpinner` epochs—requiring custom webhook callbacks or healthcheck hacks to prevent LiteLLM from triggering cold model loads during `COOLING_CUTOFF` or swapping models mid-epoch.
* Bad, because adding another Python/Prisma service container inside WSL2 increases idle RAM footprint (`~400-700 MB` in `vmmemWSL`) and slows cold startup.

## Links

* Related to [ADR-0014](0014-adopt-preemptible-host-governor-and-sticky-model-epoch-queue.md)
* Related to [ADR-0010](0010-adopt-langgraph-for-autonomous-self-reflection-loops-over-n8n-workflows.md)
