"""Hexagonal Ring 3 JSONL decision provenance adapter with monotonic D-NNN recovery."""

import json
import logging
import os
import threading
from typing import Any

from alos.adapters.outbound.audit.telemetry_tracer import _enrich_trace, _resolve_journal_path
from alos.domain.models.audit import DecisionRecord
from alos.domain.models.evaluation import RiskLevel
from alos.native import get_journal_writer

_KEYS = ("trigger", "action", *tuple(DecisionRecord.model_fields)[4:-2])


def _parse_seq(did: object) -> int:
    return int(did[2:]) if isinstance(did, str) and did[:2] == "D-" and did[2:].isdigit() else 0


def _line_seq(raw: str) -> int:
    try:
        return _parse_seq(json.loads(raw).get("decision_id"))
    except (ValueError, AttributeError):
        return 0


def _to_decision_record(*args: Any, **kwargs: Any) -> DecisionRecord:
    kw = {**dict(zip(_KEYS, args, strict=False)), **kwargs}
    act, rl = kw.pop("action"), kw["risk_level"]
    kw["action_type"] = getattr(act, "action_type", str(act))
    kw["risk_level"] = RiskLevel(getattr(rl, "value", str(rl)))
    return DecisionRecord(**kw)


class JsonlDecisionLogAdapter:
    """Append-only JSONL adapter implementing DecisionLoggerPort (Spec 036, FR-3613)."""

    def __init__(self, log_file_path: str | None = None, *, stream_logger: Any = None) -> None:
        p = _resolve_journal_path(log_file_path, "decision_log_path", "decision_log.jsonl")
        self.log_file_path, self._lock, self._writer = p, threading.Lock(), get_journal_writer(p)
        self._stream: logging.Logger | None = stream_logger
        self._counter = 0
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as fh:
                self._counter = max((_line_seq(s) for ln in fh if (s := ln.strip())), default=0)

    def log_decision_record(self, record: DecisionRecord) -> dict[str, Any]:
        """Persist an immutable DecisionRecord with monotonic D-NNN assignment."""
        with self._lock:
            self._counter = max(self._counter + 1, _parse_seq(record.decision_id))
            out = _enrich_trace(record.model_dump(mode="json"))
            out["decision_id"] = f"D-{self._counter:03d}"
            self._writer.append_record(json.dumps(out))
        if self._stream is not None:
            self._stream.info("decision %s %s", out["decision_id"], out["decision"])
        return out

    def log_decision(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Compatibility bridge constructing a DecisionRecord and delegating persistence."""
        return self.log_decision_record(_to_decision_record(*args, **kwargs))
