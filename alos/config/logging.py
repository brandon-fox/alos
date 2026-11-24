"""Twelve-Factor Factor XI structured stdout/stderr operational logging.

Spec: specs/036-hexagonal-twelve-factor-refactor/spec.md (FR-3612)
ADRs: docs/adr/0021
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Literal, TextIO

from alos.config.settings import ALOSSettings


class FactorXIFormatter(logging.Formatter):
    """Format operational log records as single-line UTC JSON or readable text."""

    def __init__(self, fmt_mode: Literal["json", "text"] = "json") -> None:
        super().__init__()
        self.fmt_mode = fmt_mode

    def format(self, record: logging.LogRecord) -> str:
        """Render a log record according to the configured Factor XI stream format."""
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        msg = record.getMessage()
        if self.fmt_mode == "text":
            return f"[{ts}] {record.levelname} {record.name}: {msg}"
        data = {"timestamp": ts, "level": record.levelname, "logger": record.name, "message": msg}
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=True)


def configure_logging(
    settings: ALOSSettings | None = None,
    *,
    stream_out: TextIO | None = None,
    stream_err: TextIO | None = None,
) -> logging.Logger:
    """Configure ALOS logger to emit <WARNING to stdout and >=WARNING to stderr."""
    cfg = settings or ALOSSettings()
    logger = logging.getLogger("alos")
    logger.handlers.clear()
    logger.setLevel(getattr(logging, cfg.log_level.upper(), logging.INFO))
    logger.propagate = False
    fmt = FactorXIFormatter(fmt_mode=cfg.log_format)
    specs = (
        (stream_out or sys.stdout, logging.DEBUG, lambda r: r.levelno < logging.WARNING),
        (stream_err or sys.stderr, logging.WARNING, None),
    )
    for stream, min_lvl, flt in specs:
        h = logging.StreamHandler(stream)
        h.setLevel(min_lvl)
        h.setFormatter(fmt)
        if flt is not None:
            h.addFilter(flt)
        logger.addHandler(h)
    return logger


def get_logger(name: str = "alos") -> logging.Logger:
    """Return a named operational logger within the ALOS logging hierarchy."""
    return logging.getLogger(name)
