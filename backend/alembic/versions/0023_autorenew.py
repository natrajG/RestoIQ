"""Auto-renewing subscriptions through Razorpay Subscriptions

Revision ID: 0023_autorenew
Revises: 0022_accounts_advance
"""
import sqlalchemy as sa
from alembic import op

revision = "0023_autorenew"
down_revision = "0022_accounts_advance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "autorenewals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("razorpay_subscription_id", sa.String(40), nullable=False, unique=True),
        sa.Column("billing_cycle", sa.String(8), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="created"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.execute('ALTER TABLE "autorenewals" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "autorenewals" FORCE ROW LEVEL SECURITY')
    op.execute(
        """CREATE POLICY tenant_isolation ON "autorenewals"
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)"""
    )
    op.create_table(
        "razorpay_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("billing_cycle", sa.String(8), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("razorpay_plan_id", sa.String(40), nullable=False),
        sa.UniqueConstraint("billing_cycle", "amount_paise"),
    )


def downgrade() -> None:
    op.drop_table("razorpay_plans")
    op.drop_table("autorenewals")
