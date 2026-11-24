"""Immutable Append-Only System Audit Logger.

Spec: specs/010-audit-and-decision-log/spec.md
Spec: specs/035-parallel-testing-and-qa-matrix/spec.md (FR-001, FR-007)
"""

from __future__ import annotations

from alos.adapters.outbound.audit.jsonl_audit_log import JsonlAuditLogAdapter


class SystemAuditLogger(JsonlAuditLogAdapter):
    """Immutable, append-only system audit logger (/logs/system_audit.jsonl)."""
