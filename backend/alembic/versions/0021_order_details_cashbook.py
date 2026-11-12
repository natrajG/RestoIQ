"""Order details, customer profile fields, petty cash and day close

Revision ID: 0021_order_details_cashbook
Revises: 0020_reminder_logs
"""
import sqlalchemy as sa
from alembic import op

revision = "0021_order_details_cashbook"
down_revision = "0020_reminder_logs"
branch_labels = None
depends_on = None


def _rls(table: str) -> None:
    op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
    op.execute(
        f"""CREATE POLICY tenant_isolation ON "{table}"
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)"""
    )


def upgrade() -> None:
    op.add_column("orders", sa.Column("covers", sa.Integer(), nullable=True))
    op.add_column("orders", sa.Column("remark", sa.String(300), nullable=True))
    op.add_column("orders", sa.Column("staff_name", sa.String(120), nullable=True))
    op.add_column("customers", sa.Column("birthday", sa.Date(), nullable=True))
    op.add_column("customers", sa.Column("anniversary", sa.Date(), nullable=True))
    op.add_column("customers", sa.Column("gstin", sa.String(15), nullable=True))
    op.add_column("customers", sa.Column("address", sa.String(400), nullable=True))
    op.create_table(
        "petty_cash_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("restaurant_id", sa.Integer(), sa.ForeignKey("outlets.id"), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(4), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("reason", sa.String(200), nullable=False),
        sa.Column("created_by", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_petty_cash_entries_tenant_id", "petty_cash_entries", ["tenant_id"])
    op.create_index("ix_petty_cash_entries_restaurant_id", "petty_cash_entries", ["restaurant_id"])
    op.create_table(
        "day_closes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("restaurant_id", sa.Integer(), sa.ForeignKey("outlets.id"), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("opening_cash", sa.Numeric(12, 2), nullable=False),
        sa.Column("cash_sales", sa.Numeric(12, 2), nullable=False),
        sa.Column("petty_in", sa.Numeric(12, 2), nullable=False),
        sa.Column("petty_out", sa.Numeric(12, 2), nullable=False),
        sa.Column("expected_cash", sa.Numeric(12, 2), nullable=False),
        sa.Column("counted_cash", sa.Numeric(12, 2), nullable=False),
        sa.Column("difference", sa.Numeric(12, 2), nullable=False),
        sa.Column("note", sa.String(300), nullable=True),
        sa.Column("closed_by", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("restaurant_id", "business_date", name="uq_day_close_outlet_date"),
    )
    op.create_index("ix_day_closes_tenant_id", "day_closes", ["tenant_id"])
    _rls("petty_cash_entries")
    _rls("day_closes")


def downgrade() -> None:
    op.drop_table("day_closes")
    op.drop_table("petty_cash_entries")
    for c in ("address", "gstin", "anniversary", "birthday"):
        op.drop_column("customers", c)
    for c in ("staff_name", "remark", "covers"):
        op.drop_column("orders", c)
