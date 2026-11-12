"""Single plan with monthly/yearly billing; remove external POS integration data."""
from alembic import op
import sqlalchemy as sa

revision = "0015_single_plan"
down_revision = "0014_order_charges"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("plan_prices", sa.Column("yearly_price_inr", sa.Numeric(10, 2), nullable=False, server_default="5999"))
    op.add_column("subscriptions", sa.Column("billing_cycle", sa.String(length=8), nullable=False, server_default="monthly"))
    # Bills pushed or imported from other POS systems are no longer supported.
    ext = "SELECT id FROM orders WHERE source = 'external'"
    op.execute(f"DELETE FROM payments WHERE order_id IN ({ext})")
    op.execute(f"DELETE FROM order_items WHERE order_id IN ({ext})")
    op.execute("DELETE FROM orders WHERE source = 'external'")
    op.drop_column("orders", "external_id")
    op.drop_column("outlets", "pos_mode")
    op.drop_table("external_events")
    op.drop_table("integration_keys")


def downgrade() -> None:
    raise NotImplementedError("External POS integration was removed permanently")
