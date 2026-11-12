"""Store automatically generated weekly and monthly reports."""
from alembic import op
import sqlalchemy as sa

revision = "0011_generated_reports"
down_revision = "0010_camera_floor"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table("generated_reports"):
        op.create_table(
            "generated_reports",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("restaurant_id", sa.Integer(), sa.ForeignKey("outlets.id"), nullable=False),
            sa.Column("period", sa.String(length=12), nullable=False),
            sa.Column("period_end", sa.Date(), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("restaurant_id", "period", "period_end", name="uq_report_outlet_period_end"),
        )
        op.create_index("ix_generated_reports_tenant_id", "generated_reports", ["tenant_id"])
        op.create_index("ix_generated_reports_restaurant_id", "generated_reports", ["restaurant_id"])
    op.execute('ALTER TABLE "generated_reports" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "generated_reports" FORCE ROW LEVEL SECURITY')
    op.execute('DROP POLICY IF EXISTS tenant_isolation ON "generated_reports"')
    op.execute(
        '''CREATE POLICY tenant_isolation ON "generated_reports"
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)'''
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON generated_reports TO restaurant_app")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO restaurant_app")


def downgrade() -> None:
    op.execute('DROP POLICY IF EXISTS tenant_isolation ON "generated_reports"')
    op.drop_table("generated_reports")
