"""Ring 3 driven HTTP and deterministic mock n8n WorkflowOrchestratorPort adapters."""

from __future__ import annotations

from typing import Any

from alos.adapters.outbound._http import parse_http_base_url, post_json
from alos.application.ports.outbound import WorkflowOrchestratorPort
from alos.domain.models.workflow import N8nExecutionResponse as _R
from alos.integrations.n8n_client import N8nClient

_M = dict[str, Any]
_URL = "http://127.0.0.1:5678"


def _unpack(p: _M, wf: str | None) -> tuple[str, _M]:
    if wf is not None:
        return wf, p
    if set(p) == {"workflow_id", "payload"} and isinstance(p["payload"], dict):
        return str(p["workflow_id"]), p["payload"]
    return str(p.get("workflow_id", "wf-poll")), {k: v for k, v in p.items() if k != "workflow_id"}


class N8nHttpAdapter(WorkflowOrchestratorPort):
    """Real HTTP adapter posting workflow triggers to n8n webhook endpoints."""

    def __init__(
        self, base_url: str = _URL, api_key: str | None = None, timeout: float = 10.0
    ) -> None:
        self.base_url = parse_http_base_url(base_url, "n8n")
        self.api_key, self.timeout, self._val = api_key, timeout, N8nClient(mock_mode=True)

    def trigger_workflow(self, payload: _M, workflow_id: str | None = None) -> _R:
        """POST workflow payload to n8n webhook endpoint and parse N8nExecutionResponse."""
        wf, body = _unpack(payload, workflow_id)
        if err := self._val.validate_workflow_payload(wf, body):
            return _R(status_code=400, error=f"Validation Error: {err}")
        hdrs = {"X-N8N-API-KEY": self.api_key} if self.api_key else None
        try:
            code, data, rsn = post_json(f"{self.base_url}/webhook/{wf}", body, hdrs, self.timeout)
        except OSError as exc:
            return _R(status_code=503, error=str(exc))
        if code >= 400:
            return _R(status_code=code, data=data, error=str(data.get("error") or rsn))
        eid = str(data.get("execution_id", f"exec-{wf}-001"))
        return _R(status_code=code, data=data, execution_id=eid)


class N8nMockAdapter(WorkflowOrchestratorPort):
    """Deterministic in-memory mock adapter implementing WorkflowOrchestratorPort."""

    def __init__(self) -> None:
        self._client = N8nClient(mock_mode=True)

    def trigger_workflow(self, payload: _M, workflow_id: str | None = None) -> _R:
        """Simulate n8n workflow execution deterministically without network I/O."""
        return self._client.trigger_workflow(*_unpack(payload, workflow_id))
