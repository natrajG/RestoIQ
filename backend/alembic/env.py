from logging.config import fileConfig

from alembic import context
from alembic.script import ScriptDirectory
from sqlalchemy import engine_from_config, inspect, pool, text

from app.core.config import settings
from app.db import Base
from app import models  # noqa: F401

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


# Tables that carry tenant_id but are read before a tenant is known (login, webhooks, reminders), so they have no RLS.
RLS_EXEMPT = {"users", "delivery_channels", "integration_connections", "reminder_logs"}


# Objects the live schema has that the ORM models do not declare (created by raw SQL in migrations).
LEGACY_DDL = [
    """CREATE TABLE document_counters (
        id SERIAL PRIMARY KEY,
        tenant_id INTEGER NOT NULL REFERENCES organizations(id),
        restaurant_id INTEGER NOT NULL REFERENCES outlets(id),
        fy VARCHAR(8) NOT NULL,
        last_number INTEGER NOT NULL DEFAULT 0,
        CONSTRAINT uq_counter_outlet_fy UNIQUE (restaurant_id, fy))""",
    "CREATE INDEX ix_document_counters_tenant_id ON document_counters (tenant_id)",
    "ALTER TABLE razorpay_plans ADD CONSTRAINT razorpay_plans_billing_cycle_amount_paise_key UNIQUE (billing_cycle, amount_paise)",
    "ALTER TABLE tenant_profiles ADD CONSTRAINT tenant_profiles_tenant_id_key UNIQUE (tenant_id)",
]

# Server-side defaults the migrations added; the models only set them in Python.
_NOW = "now()"
SERVER_DEFAULTS = [
    *[(t, "created_at", _NOW) for t in (
        "autorenewals", "customer_ledger", "day_closes", "delivery_channels", "delivery_orders", "integration_connections",
        "integration_events", "integration_sync_jobs", "password_reset_tokens", "payment_orders", "petty_cash_entries", "reminder_logs")],
    ("autorenewals", "status", "'created'"), ("festival_calendar", "active", "true"),
    ("integration_connections", "config", "'{}'::json"), ("integration_connections", "credentials_ciphertext", "''"),
    ("integration_connections", "status", "'pending'"), ("integration_connections", "updated_at", _NOW),
    ("integration_events", "processing_status", "'received'"), ("integration_sync_jobs", "next_attempt_at", _NOW),
    ("integration_sync_jobs", "payload", "'{}'::json"), ("integration_sync_jobs", "status", "'pending'"),
    ("operational_events", "processing_attempts", "0"), ("operational_events", "processing_status", "'pending'"),
    ("operational_events", "source", "'native_pos'"), ("payment_orders", "status", "'created'"),
]


def bootstrap_fresh_database(connection) -> None:
    """Builds an empty database straight from the current models, with the same RLS and grants the migration chain
    produces, then stamps it at head. The historical chain only upgrades existing databases: 0001 itself calls
    create_all from today's models, so replaying the later migrations on top of it fails."""
    Base.metadata.create_all(bind=connection)
    for stmt in LEGACY_DDL:
        connection.execute(text(stmt))
    for table, column, default in SERVER_DEFAULTS:
        connection.execute(text(f'ALTER TABLE "{table}" ALTER COLUMN "{column}" SET DEFAULT {default}'))
    inspector = inspect(connection)
    for name in sorted(inspector.get_table_names()):
        if name in RLS_EXEMPT or "tenant_id" not in {c["name"] for c in inspector.get_columns(name)}:
            continue
        connection.execute(text(f'ALTER TABLE "{name}" ENABLE ROW LEVEL SECURITY'))
        connection.execute(text(f'ALTER TABLE "{name}" FORCE ROW LEVEL SECURITY'))
        connection.execute(text(
            f'''CREATE POLICY tenant_isolation ON "{name}"
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)'''))
    connection.execute(text("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'restaurant_app') THEN
        GRANT USAGE ON SCHEMA public TO restaurant_app;
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO restaurant_app;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO restaurant_app;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO restaurant_app;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO restaurant_app;
      END IF; END $$"""))


def run_migrations_offline() -> None:
    url = settings.migration_database_url or settings.database_url
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = settings.migration_database_url or settings.database_url
    connectable = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        tables = set(inspect(connection).get_table_names())
        fresh = "alembic_version" not in tables and "organizations" not in tables
        with context.begin_transaction():
            if fresh:
                bootstrap_fresh_database(connection)
                context.get_context().stamp(ScriptDirectory.from_config(config), "head")
            else:
                context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
