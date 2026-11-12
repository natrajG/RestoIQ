"""Add camera reference image for table-zone drawing."""
from alembic import op
import sqlalchemy as sa

revision = "0009_camera_reference_image"
down_revision = "0008_user_full_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    cols = [c["name"] for c in sa.inspect(op.get_bind()).get_columns("cameras")]
    if "reference_image_path" not in cols:
        op.add_column("cameras", sa.Column("reference_image_path", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("cameras", "reference_image_path")
