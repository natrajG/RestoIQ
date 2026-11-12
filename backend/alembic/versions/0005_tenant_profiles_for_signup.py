"""Add tenant profiles captured at self-serve signup."""
from alembic import op
import sqlalchemy as sa

revision = "0005_tenant_profiles"
down_revision = "0004_festival_calendar"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fresh databases already get this table from 0001's metadata create_all.
    if not sa.inspect(op.get_bind()).has_table("tenant_profiles"):
        op.create_table(
            "tenant_profiles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False, unique=True),
            sa.Column("owner_name", sa.String(length=120), nullable=False),
            sa.Column("mobile", sa.String(length=16), nullable=False),
            sa.Column("address_line", sa.String(length=300), nullable=False),
            sa.Column("city", sa.String(length=80), nullable=False),
            sa.Column("state_code", sa.String(length=4), nullable=False),
            sa.Column("pincode", sa.String(length=10), nullable=False),
            sa.Column("gstin", sa.String(length=15), nullable=True),
            sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_tenant_profiles_tenant_id", "tenant_profiles", ["tenant_id"])
    op.execute('ALTER TABLE "tenant_profiles" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "tenant_profiles" FORCE ROW LEVEL SECURITY')
    op.execute('DROP POLICY IF EXISTS tenant_isolation ON "tenant_profiles"')
    op.execute(
        '''CREATE POLICY tenant_isolation ON "tenant_profiles"
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)'''
    )


def downgrade() -> None:
    op.execute('DROP POLICY IF EXISTS tenant_isolation ON "tenant_profiles"')
    op.drop_table("tenant_profiles")
