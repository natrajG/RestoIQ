"""Add festival calendar for demand-aware menu intelligence."""
from alembic import op
import sqlalchemy as sa

revision = "0004_festival_calendar"
down_revision = "0003_financial_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "festival_calendar",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("restaurant_id", sa.Integer(), sa.ForeignKey("outlets.id"), nullable=True),
        sa.Column("state_code", sa.String(length=4), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("notes", sa.String(length=300), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_festival_calendar_tenant_id", "festival_calendar", ["tenant_id"])
    op.create_index("ix_festival_calendar_restaurant_id", "festival_calendar", ["restaurant_id"])
    op.execute('ALTER TABLE "festival_calendar" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "festival_calendar" FORCE ROW LEVEL SECURITY')
    op.execute(
        '''CREATE POLICY tenant_isolation ON "festival_calendar"
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)'''
    )


def downgrade() -> None:
    op.execute('DROP POLICY IF EXISTS tenant_isolation ON "festival_calendar"')
    op.drop_index("ix_festival_calendar_restaurant_id", table_name="festival_calendar")
    op.drop_index("ix_festival_calendar_tenant_id", table_name="festival_calendar")
    op.drop_table("festival_calendar")
