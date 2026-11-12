"""Renewal reminder log

Revision ID: 0020_reminder_logs
Revises: 0019_password_reset
"""
import sqlalchemy as sa
from alembic import op

revision = "0020_reminder_logs"
down_revision = "0019_password_reset"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reminder_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("days_left", sa.Integer(), nullable=True),
        sa.Column("to_email", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_reminder_logs_tenant_id", "reminder_logs", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("reminder_logs")
