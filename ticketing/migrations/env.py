"""
Alembic env.py for GRM Ticketing System.
Scoped to ticketing.* schema only — never touches public.* tables.
"""

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, text

# Ensure repo root is on sys.path
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ticketing.config.settings import get_settings
from ticketing.models.base import Base
import ticketing.models  # noqa: F401 — registers all models with metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def include_object(object, name, type_, reflected, compare_to):
    """Only migrate ticketing.* — never touch public.* schema."""
    if type_ == "table":
        return getattr(object, "schema", None) == "ticketing"
    return True


def run_migrations_offline() -> None:
    settings = get_settings()
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_object=include_object,
        version_table_schema="ticketing",
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    settings = get_settings()
    connectable = create_engine(settings.database_url, pool_pre_ping=True)

    with connectable.connect() as connection:
        # Ensure ticketing schema exists before migrations run
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS ticketing"))
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_object=include_object,
            version_table_schema="ticketing",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
