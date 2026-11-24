"""RED-first unit and live loopback HTTP tests for PR-12a outbound adapters (Spec 036)."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest

import alos.adapters.outbound.integrations as ig
import alos.application.ports.outbound as ports
from alos.adapters.outbound import llm as llm_mod


class _PingHandler:
    def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"status": "SUCCESS", "pong": payload.get("msg", "")}


@pytest.mark.mocked
def test_mcp_n8n_mock_and_ollama_adapters() -> None:
    """Verify MCPGatewayAdapter, N8nMockAdapter, and OllamaLLMAdapter mock & validation paths."""
    registry = ig.ToolHandlerRegistry.default()
    gw = ig.MCPGatewayAdapter(registry=registry)
    assert isinstance(gw, ports.MCPGatewayPort) and len(registry.list_tools()) == 5
    for tool_name in list(registry.handlers):
        assert gw.execute_tool(tool_name, {"title": "T", "query": "q"})["status"] == "SUCCESS"
    assert gw.execute_tool("missing", {})["status"] == "UNKNOWN_TOOL"
    gw.register_handler("ping", _PingHandler())
    assert gw.execute_tool("ping", {"msg": "ok"})["pong"] == "ok"

    n8n = ig.N8nMockAdapter()
    assert isinstance(n8n, ports.WorkflowOrchestratorPort)
    assert n8n.trigger_workflow({"workflow_id": "wf-human-approval-gate"}).status_code == 400
    valid_gate = {"workflow_id": "wf-human-approval-gate", "task_id": "1", "action_type": "x"}
    assert n8n.trigger_workflow(valid_gate).status_code == 200
    assert n8n.trigger_workflow({"force_fail": True}).status_code == 500
    assert n8n.trigger_workflow({"api_key": "k"}, workflow_id="wf-1").status_code == 200
    assert (
        n8n.trigger_workflow({"workflow_id": "wf-1", "payload": {"api_key": "k"}}).status_code
        == 200
    )

    bot = llm_mod.OllamaLLMAdapter(model="ollama/qwen2.5:7b", mock_mode=True)
    assert "hi" in bot.generate("hi")["response"]
    assert "yo" in bot.chat([{"role": "user", "content": "yo"}])["message"]["content"]
    with pytest.raises(ValueError, match="http"):
        llm_mod.OllamaLLMAdapter(base_url="file:///x")
    with pytest.raises(ValueError, match="http"):
        ig.N8nHttpAdapter(base_url="ftp://x")


class _LoopbackHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        body: dict[str, Any] = json.loads(raw.decode("utf-8")) if raw else {}
        key = self.headers.get("X-N8N-API-KEY", "")
        routes: dict[str, tuple[int, dict[str, Any]]] = {
            "/webhook/wf-fail": (500, {"error": "upstream failure"}),
            "/api/generate": (200, {"model": body.get("model", ""), "response": "live-gen"}),
            "/api/chat": (
                200,
                {"model": body.get("model", ""), "message": {"content": "live-chat"}},
            ),
        }
        code, out = routes.get(self.path, (200, {"execution_id": "e1", "key": key, "echo": body}))
        data = json.dumps(out).encode("utf-8")
        self.send_response(code)
        for h, v in (("Content-Type", "application/json"), ("Content-Length", str(len(data)))):
            self.send_header(h, v)
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: object) -> None:
        return


@pytest.mark.live
def test_live_loopback_http_n8n_and_ollama_adapters() -> None:
    """Verify N8nHttpAdapter and OllamaLLMAdapter over live loopback HTTPServer."""
    srv = HTTPServer(("127.0.0.1", 0), _LoopbackHandler)
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        n8n = ig.N8nHttpAdapter(base_url=base, api_key="k1", timeout=5.0)
        resp = n8n.trigger_workflow({"workflow_id": "wf-live", "x": 1})
        assert resp.status_code == 200 and resp.execution_id == "e1" and resp.data["key"] == "k1"
        assert n8n.trigger_workflow({"workflow_id": "wf-human-approval-gate"}).status_code == 400
        assert n8n.trigger_workflow({"workflow_id": "wf-fail"}).status_code == 500
        bot = llm_mod.OllamaLLMAdapter(base_url=base, model="qwen2.5:7b", mock_mode=False)
        assert bot.generate("hi", system="brief")["response"] == "live-gen"
        assert bot.chat([{"role": "user", "content": "hi"}])["message"]["content"] == "live-chat"
        with pytest.raises(RuntimeError, match="Ollama HTTP 500"):
            bot._call("/webhook/wf-fail", {"model": "x"})
    finally:
        srv.shutdown()
        srv.server_close()
    assert ig.N8nHttpAdapter(base_url=base, timeout=0.5).trigger_workflow({}).status_code == 503
