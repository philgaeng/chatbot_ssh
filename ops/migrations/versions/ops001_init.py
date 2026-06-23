# Safe to run: only creates/modifies ops.* objects + the scoped ops_app role
# Does NOT touch: grievances, complainants, public.* or ticketing.* tables (read-only grants only)
"""ops schema + system_health_checks + ops_app scoped role

Creates the dedicated `ops` schema, the system_health_checks table, and a
least-privilege `ops_app` role: read/write on ops.*, read-only on the reporting
tables the daily ops report needs.

Revision ID: ops001_init
Revises:
Create Date: 2026-06-23
"""
from __future__ import annotations

import os
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "ops001_init"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS ops")

    op.create_table(
        "system_health_checks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("check_name", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("value_json", JSONB(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema="ops",
    )
    op.create_index(
        "ix_health_checks_name_time",
        "system_health_checks",
        ["check_name", "checked_at"],
        schema="ops",
    )

    # ── Scoped role: ops_app ──────────────────────────────────────────────────
    # Password sourced from OPS_DB_PASSWORD env (loaded via env.local). If unset,
    # the role is created without a password and the operator must set one before
    # the ops container can log in.
    ops_pw = os.environ.get("OPS_DB_PASSWORD", "").replace("'", "''")
    pw_clause = f"PASSWORD '{ops_pw}'" if ops_pw else ""
    op.execute(
        f"""
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ops_app') THEN
            CREATE ROLE ops_app LOGIN {pw_clause};
          ELSE
            {"ALTER ROLE ops_app WITH PASSWORD '" + ops_pw + "';" if ops_pw else "RAISE NOTICE 'ops_app exists; password unchanged';"}
          END IF;
        END $$;
        """
    )

    # Full r/w within ops.* (existing + future tables created by the migration role).
    op.execute("GRANT USAGE ON SCHEMA ops TO ops_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA ops TO ops_app")
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA ops GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ops_app")

    # Read-only on reporting tables (guarded — schemas/tables may be created by other streams).
    op.execute("GRANT USAGE ON SCHEMA public TO ops_app")
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.schemata "
        "WHERE schema_name = 'ticketing') THEN GRANT USAGE ON SCHEMA ticketing TO ops_app; "
        "END IF; END $$;"
    )
    for tbl in ("public.grievances", "public.task_tracking", "public.file_attachments",
                "ticketing.tickets", "ticketing.ticket_events"):
        op.execute(
            f"DO $$ BEGIN IF to_regclass('{tbl}') IS NOT NULL THEN "
            f"GRANT SELECT ON {tbl} TO ops_app; END IF; END $$;"
        )


def downgrade() -> None:
    op.drop_index("ix_health_checks_name_time", table_name="system_health_checks", schema="ops")
    op.drop_table("system_health_checks", schema="ops")
    # Role/grants intentionally left in place on downgrade (other objects may depend on it).
