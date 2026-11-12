"""Add order idempotency and event outbox state."""
from alembic import op

revision = "0002_outbox"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('ALTER TABLE "orders" ADD COLUMN IF NOT EXISTS idempotency_key varchar(160)')
    op.execute('CREATE UNIQUE INDEX IF NOT EXISTS uq_orders_tenant_idempotency ON "orders" (tenant_id, idempotency_key)')
    op.execute('ALTER TABLE "operational_events" ADD COLUMN IF NOT EXISTS source varchar(32) NOT NULL DEFAULT \'native_pos\'')
    op.execute('ALTER TABLE "operational_events" ADD COLUMN IF NOT EXISTS idempotency_key varchar(160)')
    op.execute('ALTER TABLE "operational_events" ADD COLUMN IF NOT EXISTS processing_status varchar(24) NOT NULL DEFAULT \'pending\'')
    op.execute('ALTER TABLE "operational_events" ADD COLUMN IF NOT EXISTS processing_attempts integer NOT NULL DEFAULT 0')
    op.execute('ALTER TABLE "operational_events" ADD COLUMN IF NOT EXISTS last_processing_error text')
    op.execute('CREATE INDEX IF NOT EXISTS ix_operational_events_processing_status ON "operational_events" (processing_status)')
    op.execute('CREATE UNIQUE INDEX IF NOT EXISTS uq_operational_events_tenant_source_key ON "operational_events" (tenant_id, source, idempotency_key)')


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS uq_operational_events_tenant_source_key')
    op.execute('DROP INDEX IF EXISTS ix_operational_events_processing_status')
    op.execute('ALTER TABLE "operational_events" DROP COLUMN IF EXISTS last_processing_error')
    op.execute('ALTER TABLE "operational_events" DROP COLUMN IF EXISTS processing_attempts')
    op.execute('ALTER TABLE "operational_events" DROP COLUMN IF EXISTS processing_status')
    op.execute('ALTER TABLE "operational_events" DROP COLUMN IF EXISTS idempotency_key')
    op.execute('ALTER TABLE "operational_events" DROP COLUMN IF EXISTS source')
    op.execute('DROP INDEX IF EXISTS uq_orders_tenant_idempotency')
    op.execute('ALTER TABLE "orders" DROP COLUMN IF EXISTS idempotency_key')
