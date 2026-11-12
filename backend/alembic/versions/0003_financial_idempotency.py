"""Add idempotency keys to native payments and refunds."""
from alembic import op
import sqlalchemy as sa

revision = "0003_financial_idempotency"
down_revision = "0002_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("idempotency_key", sa.String(length=160), nullable=True))
    op.add_column("refunds", sa.Column("idempotency_key", sa.String(length=160), nullable=True))
    op.create_index(
        "uq_payments_tenant_order_idempotency",
        "payments",
        ["tenant_id", "order_id", "idempotency_key"],
        unique=True,
    )
    op.create_index(
        "uq_refunds_tenant_order_idempotency",
        "refunds",
        ["tenant_id", "order_id", "idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_refunds_tenant_order_idempotency", table_name="refunds")
    op.drop_index("uq_payments_tenant_order_idempotency", table_name="payments")
    op.drop_column("refunds", "idempotency_key")
    op.drop_column("payments", "idempotency_key")
