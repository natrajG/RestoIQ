"""Per-outlet, per-financial-year consecutive bill numbers."""
from alembic import op
import sqlalchemy as sa

revision = "0012_document_counters"
down_revision = "0011_generated_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table("document_counters"):
        op.create_table(
            "document_counters",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("restaurant_id", sa.Integer(), sa.ForeignKey("outlets.id"), nullable=False),
            sa.Column("fy", sa.String(length=8), nullable=False),
            sa.Column("last_number", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("restaurant_id", "fy", name="uq_counter_outlet_fy"),
        )
        op.create_index("ix_document_counters_tenant_id", "document_counters", ["tenant_id"])
    op.execute('ALTER TABLE "document_counters" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "document_counters" FORCE ROW LEVEL SECURITY')
    op.execute('DROP POLICY IF EXISTS tenant_isolation ON "document_counters"')
    op.execute(
        '''CREATE POLICY tenant_isolation ON "document_counters"
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)'''
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON document_counters TO restaurant_app")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO restaurant_app")


def downgrade() -> None:
    op.execute('DROP POLICY IF EXISTS tenant_isolation ON "document_counters"')
    op.drop_table("document_counters")
