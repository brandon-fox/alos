"""Ring 3 driven Ollama loopback HTTP adapter (/api/generate & /api/chat) with mock fallback."""

from __future__ import annotations

from typing import Any

from alos.adapters.outbound._http import parse_http_base_url, post_json

_M = dict[str, Any]
_U = "http://127.0.0.1:11434"


class OllamaLLMAdapter:
    """Local-first Ollama HTTP client supporting /api/generate, /api/chat, and mock mode."""

    def __init__(
        self,
        base_url: str = _U,
        model: str = "qwen2.5:7b",
        mock_mode: bool = False,
        timeout: float = 15.0,
    ) -> None:
        self.base_url = parse_http_base_url(base_url, "Ollama")
        self.model, self.mock_mode, self.timeout = model.removeprefix("ollama/"), mock_mode, timeout

    def _call(self, path: str, body: _M) -> _M:
        code, data, rsn = post_json(f"{self.base_url}{path}", body, timeout=self.timeout)
        if code >= 400:
            raise RuntimeError(f"Ollama HTTP {code}: {rsn}")
        return data

    def generate(self, prompt: str, *, model: str | None = None, system: str | None = None) -> _M:
        """Invoke /api/generate (non-streaming) or return deterministic mock completion."""
        m = (model or self.model).removeprefix("ollama/")
        if self.mock_mode:
            return {"model": m, "response": f"[mock:{m}] {prompt}", "done": True}
        ext = {"system": system} if system else {}
        return self._call("/api/generate", {"model": m, "prompt": prompt, "stream": False, **ext})

    def chat(self, messages: list[dict[str, str]], *, model: str | None = None) -> _M:
        """Invoke /api/chat (non-streaming) or return deterministic mock assistant message."""
        m = (model or self.model).removeprefix("ollama/")
        if self.mock_mode:
            txt = messages[-1].get("content", "") if messages else ""
            msg = {"role": "assistant", "content": f"[mock:{m}] {txt}"}
            return {"model": m, "message": msg, "done": True}
        return self._call("/api/chat", {"model": m, "messages": messages, "stream": False})
