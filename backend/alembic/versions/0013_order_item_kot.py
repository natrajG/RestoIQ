"""KOT number and cancellation state on order items."""
from alembic import op
import sqlalchemy as sa

revision = "0013_order_item_kot"
down_revision = "0012_document_counters"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("order_items", sa.Column("kot_no", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("order_items", sa.Column("status", sa.String(length=16), nullable=False, server_default="active"))
    op.add_column("order_items", sa.Column("cancel_reason", sa.String(length=300), nullable=True))


def downgrade() -> None:
    op.drop_column("order_items", "cancel_reason")
    op.drop_column("order_items", "status")
    op.drop_column("order_items", "kot_no")
