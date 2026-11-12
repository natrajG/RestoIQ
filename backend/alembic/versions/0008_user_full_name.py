"""Add optional full name to users."""
from alembic import op
import sqlalchemy as sa

revision = "0008_user_full_name"
down_revision = "0007_platform_billing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    cols = [c["name"] for c in sa.inspect(op.get_bind()).get_columns("users")]
    if "full_name" not in cols:
        op.add_column("users", sa.Column("full_name", sa.String(length=120), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "full_name")
