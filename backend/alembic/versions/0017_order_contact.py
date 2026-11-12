"""customer contact and delivery address on orders

Revision ID: 0017_order_contact
Revises: 0016_menu_options
"""
import sqlalchemy as sa
from alembic import op

revision = "0017_order_contact"
down_revision = "0016_menu_options"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("contact_name", sa.String(120), nullable=True))
    op.add_column("orders", sa.Column("contact_phone", sa.String(20), nullable=True))
    op.add_column("orders", sa.Column("delivery_address", sa.String(400), nullable=True))


def downgrade() -> None:
    for c in ("delivery_address", "contact_phone", "contact_name"):
        op.drop_column("orders", c)
