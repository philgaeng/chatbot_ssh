"""
Alembic env.py for the ops (monitoring) schema.
Scoped to ops.* only — never touches public.* or ticketing.* tables.
"""

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, text

# Ensure repo root is on sys.path
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ops.config import get_settings
from ops.models import OpsBase
import ops.models  # noqa: F401 — registers ops models with metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = OpsBase.metadata


def include_object(object, name, type_, reflected, compare_to):
    """Only migrate ops.* — never touch public.* / ticketing.* schemas."""
    if type_ == "table":
        return getattr(object, "schema", None) == "ops"
    return True


def _admin_url() -> str:
    """
    Migrations create the schema/role/grants, so they must run as an admin role,
    not as ops_app. Prefer POSTGRES_* (the superuser-ish app role) over ops_db_*.
    """
    s = get_settings()
    return (
        f"postgresql+psycopg2://{s.postgres_user}:{s.postgres_password}"
        f"@{s.postgres_host}:{s.postgres_port}/{s.postgres_db}"
    )


def run_migrations_offline() -> None:
    context.configure(
        url=_admin_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_object=include_object,
        version_table="alembic_version_ops",
        version_table_schema="ops",
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(_admin_url(), pool_pre_ping=True)
    with connectable.connect() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS ops"))
        connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_object=include_object,
            version_table="alembic_version_ops",
            version_table_schema="ops",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
