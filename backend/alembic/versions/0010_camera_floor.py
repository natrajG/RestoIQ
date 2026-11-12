"""Attach cameras to floors so several cameras can cover one floor."""
from alembic import op
import sqlalchemy as sa

revision = "0010_camera_floor"
down_revision = "0009_camera_reference_image"
branch_labels = None
depends_on = None


def upgrade() -> None:
    cols = [c["name"] for c in sa.inspect(op.get_bind()).get_columns("cameras")]
    if "floor_id" not in cols:
        op.add_column("cameras", sa.Column("floor_id", sa.Integer(), sa.ForeignKey("floors.id"), nullable=True))
        op.create_index("ix_cameras_floor_id", "cameras", ["floor_id"])


def downgrade() -> None:
    op.drop_index("ix_cameras_floor_id", table_name="cameras")
    op.drop_column("cameras", "floor_id")
