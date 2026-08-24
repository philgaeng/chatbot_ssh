# SPDX-License-Identifier: Apache-2.0
# Safe to run: only GRANTs to the ops.* stream's own `ops_app` role
# Does NOT create, alter or drop any table in any schema

"""ops_app grants for the daily report's reporting tables

Revision ID: ops003_reportgrants
Revises: ops002_depfindings
Create Date: 2026-08-24

⚠ WHY THIS EXISTS, AND WHY IT IS NOT A ONE-LINE ADDITION TO ops001.

ops001 already grants SELECT on `ticketing.tickets` — and `ops_app` did not have it. The
grant is wrapped in `IF to_regclass(...) IS NOT NULL`, which is correct (the ticketing
stream may not have run yet) and **silently skips** when the table is absent. On a stack
where ops migrated before ticketing, the grant never happened and nothing said so. Re-running
ops001 is not an option; a forward migration is.

The daily report also queries four tables ops001 never listed at all —
`ticket_overdue_episodes`, `ticket_files`, `admin_audit_log`, and `keycloak.event_entity` —
so those rows have never returned a number on any deployment.

Idempotent and guarded the same way, but the guard now *reports* what it skipped instead of
passing over it in silence.
"""
from alembic import op

revision = "ops003_reportgrants"
down_revision = "ops002_depfindings"
branch_labels = None
depends_on = None

# Every table the daily ops report reads (ops/reports.py). Aggregate counts only — the report
# is verified PII-free (privacy-assessment.md, leg L13), and SELECT on a table is what a
# `count(*)` needs.
REPORT_TABLES = (
    "public.grievances",
    "public.task_tracking",
    "public.file_attachments",
    "ticketing.tickets",
    "ticketing.ticket_events",
    "ticketing.ticket_overdue_episodes",
    "ticketing.ticket_files",
    "ticketing.admin_audit_log",
)

# Officer login / login-failure counts. The keycloak schema is owned by Keycloak itself, not by
# any of our three migration streams — we only ever read it.
KEYCLOAK_TABLES = ("keycloak.event_entity",)


def upgrade() -> None:
    for schema in ("public", "ticketing", "keycloak"):
        op.execute(
            f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.schemata "
            f"WHERE schema_name = '{schema}') THEN "
            f"GRANT USAGE ON SCHEMA {schema} TO ops_app; "
            f"ELSE RAISE NOTICE 'ops003: schema {schema} absent — USAGE not granted'; "
            f"END IF; END $$;"
        )

    for tbl in REPORT_TABLES + KEYCLOAK_TABLES:
        op.execute(
            f"DO $$ BEGIN IF to_regclass('{tbl}') IS NOT NULL THEN "
            f"GRANT SELECT ON {tbl} TO ops_app; "
            f"ELSE RAISE WARNING 'ops003: {tbl} absent — SELECT not granted, the daily "
            f"report row that reads it will render n/a'; "
            f"END IF; END $$;"
        )


def downgrade() -> None:
    for tbl in REPORT_TABLES + KEYCLOAK_TABLES:
        op.execute(
            f"DO $$ BEGIN IF to_regclass('{tbl}') IS NOT NULL THEN "
            f"REVOKE SELECT ON {tbl} FROM ops_app; END IF; END $$;"
        )
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.schemata "
        "WHERE schema_name = 'keycloak') THEN REVOKE USAGE ON SCHEMA keycloak FROM ops_app; "
        "END IF; END $$;"
    )
