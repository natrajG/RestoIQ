"""Universal integration engine: connections, events, outbox jobs, external id mappings

Revision ID: 0025_integration_engine
Revises: 0024_delivery_channels
"""
import sqlalchemy as sa
from alembic import op

revision = "0025_integration_engine"
down_revision = "0024_delivery_channels"
branch_labels = None
depends_on = None

TENANT_TABLES = ("integration_events", "integration_sync_jobs", "integration_external_ids")


def _tenant():
    return sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False, index=True)


def _conn():
    return sa.Column("connection_id", sa.Integer(), sa.ForeignKey("integration_connections.id"), nullable=False, index=True)


def upgrade() -> None:
    now = sa.func.now()
    op.create_table(
        "integration_connections",
        sa.Column("id", sa.Integer(), primary_key=True), _tenant(),
        sa.Column("restaurant_id", sa.Integer(), sa.ForeignKey("outlets.id"), index=True),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("credentials_ciphertext", sa.Text(), nullable=False, server_default=""),
        sa.Column("config", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("webhook_token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("last_error", sa.String(300)),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("circuit_open_until", sa.DateTime(timezone=True)),
        sa.Column("last_connected_at", sa.DateTime(timezone=True)),
        sa.Column("last_sync_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.UniqueConstraint("tenant_id", "restaurant_id", "provider", name="uq_integration_scope_provider"),
    )
    op.create_table(
        "integration_events",
        sa.Column("id", sa.Integer(), primary_key=True), _tenant(), _conn(),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("external_event_id", sa.String(120), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("processing_status", sa.String(16), nullable=False, server_default="received"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.String(300)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now, index=True),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("connection_id", "external_event_id", name="uq_integration_event_once"),
    )
    op.create_table(
        "integration_sync_jobs",
        sa.Column("id", sa.Integer(), primary_key=True), _tenant(), _conn(),
        sa.Column("operation", sa.String(60), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="pending", index=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.Column("error_message", sa.String(300)),
        sa.Column("result", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("connection_id", "idempotency_key", name="uq_integration_job_idem"),
    )
    op.create_table(
        "integration_external_ids",
        sa.Column("id", sa.Integer(), primary_key=True), _tenant(), _conn(),
        sa.Column("entity_type", sa.String(24), nullable=False),
        sa.Column("local_id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(120), nullable=False),
        sa.UniqueConstraint("connection_id", "entity_type", "local_id", name="uq_integration_map_local"),
        sa.UniqueConstraint("connection_id", "entity_type", "external_id", name="uq_integration_map_external"),
    )
    for table in TENANT_TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
        op.execute(
            f"""CREATE POLICY tenant_isolation ON "{table}"
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)"""
        )


def downgrade() -> None:
    for table in reversed(TENANT_TABLES):
        op.drop_table(table)
    op.drop_table("integration_connections")
