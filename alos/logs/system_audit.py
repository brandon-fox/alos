import json
import os
from datetime import datetime
from typing import Any


class SystemAuditLogger:
    """Immutable, append-only system audit logger (/logs/system_audit.jsonl)."""

    def __init__(self, log_file_path: str | None = None):
        if log_file_path:
            self.log_file_path = log_file_path
        else:
            self.log_file_path = os.path.join(os.getcwd(), "logs", "system_audit.jsonl")

        # Ensure log folder exists
        os.makedirs(os.path.dirname(self.log_file_path), exist_ok=True)

    def log_event(
        self,
        step: str,
        status: str,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        record = {
            "timestamp": datetime.now().isoformat(),
            "step": step,
            "status": status,
            "reason": reason,
            "metadata": metadata or {},
        }
        with open(self.log_file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        return record
