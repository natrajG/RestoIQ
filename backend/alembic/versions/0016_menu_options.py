"""Item variants and add-ons."""
from alembic import op
import sqlalchemy as sa

revision = "0016_menu_options"
down_revision = "0015_single_plan"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "menu_options",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("menu_item_id", sa.Integer(), sa.ForeignKey("menu_items.id"), nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.create_index("ix_menu_options_tenant_id", "menu_options", ["tenant_id"])
    op.create_index("ix_menu_options_menu_item_id", "menu_options", ["menu_item_id"])
    op.execute('ALTER TABLE "menu_options" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "menu_options" FORCE ROW LEVEL SECURITY')
    op.execute(
        """CREATE POLICY tenant_isolation ON "menu_options"
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)"""
    )
    op.add_column("order_items", sa.Column("variant_name", sa.String(length=80), nullable=True))
    op.add_column("order_items", sa.Column("addons", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("order_items", "addons")
    op.drop_column("order_items", "variant_name")
    op.drop_table("menu_options")
