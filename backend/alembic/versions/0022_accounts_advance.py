"""Complimentary items, customer account ledger, advance orders, petty cash categories

Revision ID: 0022_accounts_advance
Revises: 0021_order_details_cashbook
"""
import sqlalchemy as sa
from alembic import op

revision = "0022_accounts_advance"
down_revision = "0021_order_details_cashbook"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("complimentary_reason", sa.String(300), nullable=True))
    op.add_column("order_items", sa.Column("complimentary", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("petty_cash_entries", sa.Column("category", sa.String(40), nullable=True))
    op.add_column("petty_cash_entries", sa.Column("pay_method", sa.String(16), nullable=False, server_default="cash"))
    op.create_table(
        "customer_ledger",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("restaurant_id", sa.Integer(), sa.ForeignKey("outlets.id"), nullable=False, index=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False, index=True),
        sa.Column("kind", sa.String(6), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("method", sa.String(16), nullable=True),
        sa.Column("remark", sa.String(200), nullable=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("created_by", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.execute('ALTER TABLE "customer_ledger" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "customer_ledger" FORCE ROW LEVEL SECURITY')
    op.execute(
        """CREATE POLICY tenant_isolation ON "customer_ledger"
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)"""
    )


def downgrade() -> None:
    op.drop_table("customer_ledger")
    op.drop_column("petty_cash_entries", "pay_method")
    op.drop_column("petty_cash_entries", "category")
    op.drop_column("order_items", "complimentary")
    op.drop_column("orders", "complimentary_reason")
    op.drop_column("orders", "scheduled_for")
