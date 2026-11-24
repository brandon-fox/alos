"""Shared stdlib HTTP JSON helper for Ring 3 outbound HTTP adapters."""

from __future__ import annotations

import http.client
import json
from typing import Any
from urllib.parse import urlsplit

_Map = dict[str, Any]


def parse_http_base_url(base_url: str, label: str) -> str:
    """Validate an http(s) base URL and return it without trailing slashes."""
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{label} base_url must use http(s), got {base_url!r}")
    return base_url.rstrip("/")


def post_json(
    url: str,
    body: _Map,
    headers: dict[str, str] | None = None,
    timeout: float = 10.0,
) -> tuple[int, _Map, str]:
    """POST a JSON payload over validated http(s) using stdlib http.client."""
    parsed = urlsplit(url)
    path = f"{parsed.path or '/'}{f'?{parsed.query}' if parsed.query else ''}"
    hdrs = {"Content-Type": "application/json", **(headers or {})}
    conn_cls = (
        http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    )
    conn = conn_cls(parsed.netloc, timeout=timeout)
    try:
        conn.request("POST", path, json.dumps(body).encode("utf-8"), hdrs)
        resp = conn.getresponse()
        txt = resp.read().decode("utf-8", errors="replace").strip()
        return resp.status, (json.loads(txt) if txt.startswith("{") else {}), resp.reason
    finally:
        conn.close()
