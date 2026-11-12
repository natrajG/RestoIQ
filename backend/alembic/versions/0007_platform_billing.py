"""Add plan prices and invoices for the platform admin console."""
from alembic import op
import sqlalchemy as sa

revision = "0007_platform_billing"
down_revision = "0006_integration_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("plan_prices"):
        op.create_table(
            "plan_prices",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("plan_name", sa.String(length=80), nullable=False, unique=True),
            sa.Column("price_inr", sa.Numeric(10, 2), nullable=False),
            sa.Column("gst_percent", sa.Numeric(5, 2), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
    if not inspector.has_table("invoices"):
        op.create_table(
            "invoices",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("number", sa.String(length=24), nullable=False, unique=True),
            sa.Column("plan_name", sa.String(length=80), nullable=False),
            sa.Column("outlets", sa.Integer(), nullable=False),
            sa.Column("subtotal", sa.Numeric(12, 2), nullable=False),
            sa.Column("gst", sa.Numeric(12, 2), nullable=False),
            sa.Column("total", sa.Numeric(12, 2), nullable=False),
            sa.Column("status", sa.String(length=12), nullable=False),
            sa.Column("period_start", sa.Date(), nullable=False),
            sa.Column("period_end", sa.Date(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_invoices_tenant_id", "invoices", ["tenant_id"])
    op.execute('ALTER TABLE "invoices" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "invoices" FORCE ROW LEVEL SECURITY')
    op.execute('DROP POLICY IF EXISTS tenant_isolation ON "invoices"')
    op.execute(
        '''CREATE POLICY tenant_isolation ON "invoices"
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)'''
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON plan_prices, invoices TO restaurant_app")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO restaurant_app")


def downgrade() -> None:
    op.execute('DROP POLICY IF EXISTS tenant_isolation ON "invoices"')
    op.drop_table("invoices")
    op.drop_table("plan_prices")
