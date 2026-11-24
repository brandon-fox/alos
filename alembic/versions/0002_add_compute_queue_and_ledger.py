"""Add compute_work_queue and compute_capacity_ledger tables.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-23 21:50:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "compute_work_queue",
        sa.Column("job_id", sa.String(length=120), nullable=False),
        sa.Column("repo_slug", sa.String(length=120), nullable=False),
        sa.Column("workflow_type", sa.String(length=80), nullable=False),
        sa.Column("model_tier", sa.String(length=50), nullable=False),
        sa.Column("priority", sa.Integer(), server_default="50", nullable=False),
        sa.Column("requires_merge", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("allow_cloud_overflow", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("checkpoint_ns", sa.String(length=160), nullable=True),
        sa.Column("state", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="2", nullable=False),
        sa.Column("leased_by", sa.String(length=120), nullable=True),
        sa.Column("leased_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("job_id"),
    )
    op.create_index(
        op.f("ix_compute_work_queue_repo_slug"), "compute_work_queue", ["repo_slug"], unique=False
    )
    op.create_index(
        op.f("ix_compute_work_queue_model_tier"),
        "compute_work_queue",
        ["model_tier"],
        unique=False,
    )
    op.create_index(
        op.f("ix_compute_work_queue_state"), "compute_work_queue", ["state"], unique=False
    )

    op.create_table(
        "compute_capacity_ledger",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("governor_state", sa.String(length=40), nullable=False),
        sa.Column("active_tier", sa.String(length=50), nullable=True),
        sa.Column("gpu_temp_c", sa.Float(), nullable=True),
        sa.Column("vram_temp_c", sa.Float(), nullable=True),
        sa.Column("gpu_util_pct", sa.Integer(), nullable=True),
        sa.Column("used_vram_mb", sa.Integer(), server_default="0", nullable=False),
        sa.Column("managed_vram_mb", sa.Integer(), server_default="0", nullable=False),
        sa.Column("jobs_waiting", sa.Integer(), server_default="0", nullable=False),
        sa.Column("jobs_done_delta", sa.Integer(), server_default="0", nullable=False),
        sa.Column("jobs_preempted_delta", sa.Integer(), server_default="0", nullable=False),
        sa.Column("jobs_overflow_delta", sa.Integer(), server_default="0", nullable=False),
        sa.Column("oldest_wait_seconds", sa.Float(), server_default="0.0", nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_compute_capacity_ledger_recorded_at"),
        "compute_capacity_ledger",
        ["recorded_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_compute_capacity_ledger_governor_state"),
        "compute_capacity_ledger",
        ["governor_state"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_compute_capacity_ledger_governor_state"), table_name="compute_capacity_ledger"
    )
    op.drop_index(
        op.f("ix_compute_capacity_ledger_recorded_at"), table_name="compute_capacity_ledger"
    )
    op.drop_table("compute_capacity_ledger")

    op.drop_index(op.f("ix_compute_work_queue_state"), table_name="compute_work_queue")
    op.drop_index(op.f("ix_compute_work_queue_model_tier"), table_name="compute_work_queue")
    op.drop_index(op.f("ix_compute_work_queue_repo_slug"), table_name="compute_work_queue")
    op.drop_table("compute_work_queue")
