"""Razorpay orders for subscription invoices

Revision ID: 0018_payment_orders
Revises: 0017_order_contact
"""
import sqlalchemy as sa
from alembic import op

revision = "0018_payment_orders"
down_revision = "0017_order_contact"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("razorpay_order_id", sa.String(40), nullable=False, unique=True),
        sa.Column("razorpay_payment_id", sa.String(40), nullable=True),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="created"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_payment_orders_tenant_id", "payment_orders", ["tenant_id"])
    op.create_index("ix_payment_orders_invoice_id", "payment_orders", ["invoice_id"])
    op.execute('ALTER TABLE "payment_orders" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "payment_orders" FORCE ROW LEVEL SECURITY')
    op.execute(
        """CREATE POLICY tenant_isolation ON "payment_orders"
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)"""
    )


def downgrade() -> None:
    op.drop_table("payment_orders")
