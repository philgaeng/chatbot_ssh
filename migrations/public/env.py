"""
Alembic env.py for public (default) Postgres schema — chatbot / grievance DB tables.

- Uses its own version table: alembic_version_public (in public schema).
- Never touches ticketing.* — that stream lives under ticketing/migrations/.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine

# Repo root on sys.path for backend.config
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.config.constants import DB_CONFIG  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# No SQLAlchemy models for public in this repo — revisions are hand-written (upgrade/downgrade).
target_metadata = None


def _database_url() -> str:
    from urllib.parse import quote_plus

    user = quote_plus(str(DB_CONFIG["user"]))
    password = quote_plus(str(DB_CONFIG["password"]))
    host = DB_CONFIG["host"]
    port = DB_CONFIG["port"]
    database = quote_plus(str(DB_CONFIG["database"]))
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


def include_object(object, name, type_, reflected, compare_to):
    """Only consider public schema objects; exclude ticketing.* from autogenerate (if used later)."""
    if type_ == "table":
        sch = getattr(object, "schema", None)
        return sch is None or sch == "public"
    return True


def run_migrations_offline() -> None:
    url = _database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_object=include_object,
        version_table="alembic_version_public",
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(_database_url(), pool_pre_ping=True)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_object=include_object,
            version_table="alembic_version_public",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
