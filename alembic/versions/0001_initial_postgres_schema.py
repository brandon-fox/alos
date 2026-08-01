"""Initial postgres schema revision for ALOS.

Revision ID: 0001
Revises:
Create Date: 2026-08-01 14:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. system_audit_logs
    op.create_table(
        "system_audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("step", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_system_audit_logs_step"), "system_audit_logs", ["step"], unique=False)
    op.create_index(
        op.f("ix_system_audit_logs_status"), "system_audit_logs", ["status"], unique=False
    )

    # 2. decision_records
    op.create_table(
        "decision_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("decision_id", sa.String(length=100), nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column("action_type", sa.String(length=100), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("decision", sa.String(length=20), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("constitution_articles_checked", sa.JSON(), nullable=False),
        sa.Column("preferences_checked", sa.JSON(), nullable=False),
        sa.Column("corrections_checked", sa.JSON(), nullable=False),
        sa.Column("alternatives_considered", sa.JSON(), nullable=False),
        sa.Column("self_correction_rounds", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_decision_records_decision_id"), "decision_records", ["decision_id"], unique=True
    )
    op.create_index(
        op.f("ix_decision_records_action_type"), "decision_records", ["action_type"], unique=False
    )
    op.create_index(
        op.f("ix_decision_records_decision"), "decision_records", ["decision"], unique=False
    )

    # 3. execution_states
    op.create_table(
        "execution_states",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workflow_id", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_execution_states_workflow_id"), "execution_states", ["workflow_id"], unique=False
    )
    op.create_index(
        op.f("ix_execution_states_status"), "execution_states", ["status"], unique=False
    )

    # 4. user_profiles
    op.create_table(
        "user_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("preferences", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_profiles_username"), "user_profiles", ["username"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_profiles_username"), table_name="user_profiles")
    op.drop_table("user_profiles")

    op.drop_index(op.f("ix_execution_states_status"), table_name="execution_states")
    op.drop_index(op.f("ix_execution_states_workflow_id"), table_name="execution_states")
    op.drop_table("execution_states")

    op.drop_index(op.f("ix_decision_records_decision"), table_name="decision_records")
    op.drop_index(op.f("ix_decision_records_action_type"), table_name="decision_records")
    op.drop_index(op.f("ix_decision_records_decision_id"), table_name="decision_records")
    op.drop_table("decision_records")

    op.drop_index(op.f("ix_system_audit_logs_status"), table_name="system_audit_logs")
    op.drop_index(op.f("ix_system_audit_logs_step"), table_name="system_audit_logs")
    op.drop_table("system_audit_logs")
