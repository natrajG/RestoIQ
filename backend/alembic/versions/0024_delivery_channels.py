"""Delivery aggregator channels and inbound orders

Revision ID: 0024_delivery_channels
Revises: 0023_autorenew
"""
import sqlalchemy as sa
from alembic import op

revision = "0024_delivery_channels"
down_revision = "0023_autorenew"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "delivery_channels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("restaurant_id", sa.Integer(), sa.ForeignKey("outlets.id"), nullable=False, index=True),
        sa.Column("provider", sa.String(24), nullable=False),
        sa.Column("label", sa.String(80)),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("secret_ciphertext", sa.String(300), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "delivery_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("restaurant_id", sa.Integer(), sa.ForeignKey("outlets.id"), nullable=False, index=True),
        sa.Column("channel_id", sa.Integer(), sa.ForeignKey("delivery_channels.id"), nullable=False, index=True),
        sa.Column("provider", sa.String(24), nullable=False),
        sa.Column("external_id", sa.String(80), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id")),
        sa.Column("aggregator_total", sa.Numeric(12, 2)),
        sa.Column("commission", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_mismatch", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("unmatched", sa.JSON()),
        sa.Column("raw", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("channel_id", "external_id"),
    )
    op.execute('ALTER TABLE "delivery_orders" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "delivery_orders" FORCE ROW LEVEL SECURITY')
    op.execute(
        """CREATE POLICY tenant_isolation ON "delivery_orders"
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)"""
    )


def downgrade() -> None:
    op.drop_table("delivery_orders")
    op.drop_table("delivery_channels")
