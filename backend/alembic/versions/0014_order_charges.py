"""Discount reason/type, service charge, round-off and tip on orders."""
from alembic import op
import sqlalchemy as sa

revision = "0014_order_charges"
down_revision = "0013_order_item_kot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("discount_type", sa.String(length=8), nullable=True))
    op.add_column("orders", sa.Column("discount_value", sa.Numeric(12, 2), nullable=False, server_default="0"))
    op.add_column("orders", sa.Column("discount_reason", sa.String(length=300), nullable=True))
    op.add_column("orders", sa.Column("service_charge", sa.Numeric(12, 2), nullable=False, server_default="0"))
    op.add_column("orders", sa.Column("service_charge_waived", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("orders", sa.Column("round_off", sa.Numeric(6, 2), nullable=False, server_default="0"))
    op.add_column("orders", sa.Column("tip", sa.Numeric(12, 2), nullable=False, server_default="0"))
    op.execute("UPDATE orders SET discount_type='fixed', discount_value=discount_total WHERE discount_total > 0")


def downgrade() -> None:
    for column in ("tip", "round_off", "service_charge_waived", "service_charge", "discount_reason", "discount_value", "discount_type"):
        op.drop_column("orders", column)
