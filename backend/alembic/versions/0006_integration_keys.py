"""Add per-tenant POS integration API keys."""
from alembic import op
import sqlalchemy as sa

revision = "0006_integration_keys"
down_revision = "0005_tenant_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table("integration_keys"):
        op.create_table(
            "integration_keys",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False, unique=True),
            sa.Column("key_hash", sa.String(length=64), nullable=False),
            sa.Column("key_prefix", sa.String(length=12), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_integration_keys_tenant_id", "integration_keys", ["tenant_id"])
        op.create_index("ix_integration_keys_key_hash", "integration_keys", ["key_hash"])
    op.execute('ALTER TABLE "integration_keys" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "integration_keys" FORCE ROW LEVEL SECURITY')
    op.execute('DROP POLICY IF EXISTS tenant_isolation ON "integration_keys"')
    op.execute(
        '''CREATE POLICY tenant_isolation ON "integration_keys"
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)'''
    )


def downgrade() -> None:
    op.execute('DROP POLICY IF EXISTS tenant_isolation ON "integration_keys"')
    op.drop_table("integration_keys")
