"""Measure concurrent-slot throughput per roster model on a dispatcher-owned Ollama server.

Closes the "slots per model" open item in specs/029-local-swarm-dispatcher/spec.md.
Loads each model, generates text and stops the server; it changes no system setting.

Usage (from the repository root, with the package importable):
    python scripts/swarm/bench_slots.py [model ...]
"""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from functools import partial

from alos.swarm.dispatcher import DEFAULT_ROSTER, Ollama, start_server, stop_server

PROMPT = "Write about 150 words on how to season firewood."
SLOT_COUNTS = (1, 2, 4, 8)


def generate(client: Ollama, model: str, tokens: int) -> int:
    """Generate up to ``tokens`` tokens and return how many were produced."""
    options = {"num_predict": tokens, "num_ctx": 8192}
    body = {"model": model, "prompt": PROMPT, "stream": False, "options": options}
    return int(client.call("/api/generate", body, timeout=300).get("eval_count", 0))


def placement(client: Ollama, model: str) -> str:
    """How much of the loaded model sits on the GPU."""
    for loaded in client.call("/api/ps").get("models", []):
        if loaded.get("name") == model:
            size, vram = int(loaded.get("size", 0)), int(loaded.get("size_vram", 0))
            return f"{vram / 2**30:.1f} of {size / 2**30:.1f} GB on GPU"
    return "not loaded"


def bench(model: str, port: int) -> None:
    """Print total tokens per second for each slot count, one server per count."""
    for slots in SLOT_COUNTS:
        client, proc = start_server(port, slots)
        try:
            generate(client, model, 8)  # load the model before timing
            started = time.time()
            with ThreadPoolExecutor(max_workers=slots) as pool:
                tokens = sum(pool.map(partial(generate, client, model), [200] * slots))
            rate = tokens / (time.time() - started)
            print(f"{model} slots={slots}: {rate:.0f} tok/s total, {placement(client, model)}")
        finally:
            stop_server(proc)


def main() -> int:
    """Benchmark the models named on the command line, or every roster model."""
    classes = DEFAULT_ROSTER["classes"].values()
    models = sys.argv[1:] or list(dict.fromkeys(entry["model"] for entry in classes))
    for model in models:
        bench(model, int(DEFAULT_ROSTER["server_port"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
