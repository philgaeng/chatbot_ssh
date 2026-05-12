"""public runtime prerequisite: keycloak schema for self-hosted IdP

Revision ID: pub006_keycloak_schema
Revises: pub005_runtime_prereqs_pgcrypto_timeline
Create Date: 2026-05-11

# Safe to run: only creates the `keycloak` schema (separate from public/ticketing)
# Does NOT touch: ticketing.* schema — use ticketing/migrations/alembic.ini for those
# Does NOT touch: existing public.* tables.

Why this lives in the public migration stream:
    Keycloak stores its own state (realms, clients, users, sessions) in a
    dedicated `keycloak` schema inside the same Postgres instance. Postgres
    does not auto-create schemas, so the very first time the keycloak
    container starts it errors out with `schema "keycloak" does not exist`.
    This is analogous to the `CREATE EXTENSION pgcrypto` runtime prereq in
    pub005 — infrastructure setup that has to land before the dependent
    service starts. There is no third migration stream for "infrastructure
    schemas", so we co-locate it here.

    Keycloak only runs when `--profile auth` is active. The schema is harmless
    in environments that never start Keycloak.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "pub006_keycloak_schema"
down_revision: Union[str, None] = "pub005_runtime_prereqs_pgcrypto_timeline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Schema is owned by the connecting role (typically POSTGRES_USER).
    # Keycloak connects as the same role, so it has full DDL rights.
    op.execute("CREATE SCHEMA IF NOT EXISTS keycloak;")


def downgrade() -> None:
    # CASCADE drops every table Liquibase created inside the schema.
    # Only run downgrade in a non-production environment — destroys all
    # Keycloak realms, users, sessions, etc.
    op.execute("DROP SCHEMA IF EXISTS keycloak CASCADE;")
