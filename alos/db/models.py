"""PostgreSQL database ORM models for audit, decisions, execution, and profiles."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from alos.db.base import Base


class AuditLogModel(Base):
    """ORM representation of system audit log events."""

    __tablename__ = "system_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    step: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class DecisionRecordModel(Base):
    """ORM representation of dual-loop architectural and evaluation decision records."""

    __tablename__ = "decision_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    decision_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    trigger: Mapped[str] = mapped_column(Text, nullable=False)
    action_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    constitution_articles_checked: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    preferences_checked: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    corrections_checked: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    alternatives_considered: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    self_correction_rounds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class ExecutionStateModel(Base):
    """ORM representation of workflow execution state graphs."""

    __tablename__ = "execution_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class UserProfileModel(Base):
    """ORM representation of user profiles and preferences."""

    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    preferences: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ComputeQueueJobModel(Base):
    """ORM representation of preemptible local compute queue jobs (Spec 031)."""

    __tablename__ = "compute_work_queue"

    job_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    repo_slug: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    workflow_type: Mapped[str] = mapped_column(String(80), nullable=False)
    model_tier: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    requires_merge: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allow_cloud_overflow: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    checkpoint_ns: Mapped[str | None] = mapped_column(String(160), nullable=True)
    state: Mapped[str] = mapped_column(String(32), default="queued", nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    leased_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    leased_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ComputeCapacityLedgerModel(Base):
    """ORM representation of periodic capacity, queue wait, and GPU thermal ledger entries."""

    __tablename__ = "compute_capacity_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    governor_state: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    active_tier: Mapped[str | None] = mapped_column(String(50), nullable=True)
    gpu_temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    vram_temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    gpu_util_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)
    used_vram_mb: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    managed_vram_mb: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    jobs_waiting: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    jobs_done_delta: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    jobs_preempted_delta: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    jobs_overflow_delta: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    oldest_wait_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
