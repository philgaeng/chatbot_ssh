"""projects, project_organizations, project_locations, scope includes_children, tickets.project_id

Revision ID: e8d4b6a0f291
Revises: f1a3e9c72b05
Create Date: 2026-04-23

# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
#
# Changes:
#   CREATE  ticketing.projects
#   CREATE  ticketing.project_organizations (multi-org co-ownership)
#   CREATE  ticketing.project_locations     (project ↔ location nodes join)
#   ALTER   ticketing.officer_scopes
#             - add includes_children BOOLEAN DEFAULT FALSE
#             - add project_id FK → projects (nullable, replaces project_code)
#   ALTER   ticketing.tickets
#             - add project_id FK → projects (nullable, replaces project_code)
#   DATA    seed KL_ROAD project + link to DOR/ADB and Jhapa/Morang/Sunsari districts
#           backfill tickets.project_id from project_code = 'KL_ROAD'
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "e8d4b6a0f291"
down_revision = "f1a3e9c72b05"
branch_labels = None
depends_on = None

# Stable ID for the KL_ROAD project — used in seed + backfill
KL_ROAD_PROJECT_ID = "7b0c4f10-grm-klrd-0000-000000000001"


def upgrade() -> None:
    # ── 1. ticketing.projects ─────────────────────────────────────────────────
    op.create_table(
        "projects",
        sa.Column("project_id",   sa.String(64),  nullable=False),
        sa.Column("country_code", sa.String(8),   nullable=False),
        sa.Column("short_code",   sa.String(64),  nullable=False),
        sa.Column("name",         sa.Text,        nullable=False),
        sa.Column("description",  sa.Text,        nullable=True),
        sa.Column("is_active",    sa.Boolean,     nullable=False, server_default="true"),
        sa.Column("created_at",   sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at",   sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("project_id"),
        sa.UniqueConstraint("short_code", name="uq_projects_short_code"),
        sa.ForeignKeyConstraint(
            ["country_code"], ["ticketing.countries.country_code"], ondelete="RESTRICT"
        ),
        schema="ticketing",
    )
    op.create_index("idx_projects_country",    "projects", ["country_code"], schema="ticketing")
    op.create_index("idx_projects_short_code", "projects", ["short_code"],   schema="ticketing")

    # ── 2. ticketing.project_organizations ───────────────────────────────────
    op.create_table(
        "project_organizations",
        sa.Column("project_id",      sa.String(64), nullable=False),
        sa.Column("organization_id", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("project_id", "organization_id"),
        sa.ForeignKeyConstraint(
            ["project_id"], ["ticketing.projects.project_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["ticketing.organizations.organization_id"], ondelete="CASCADE"
        ),
        schema="ticketing",
    )

    # ── 3. ticketing.project_locations ───────────────────────────────────────
    op.create_table(
        "project_locations",
        sa.Column("project_id",    sa.String(64), nullable=False),
        sa.Column("location_code", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("project_id", "location_code"),
        sa.ForeignKeyConstraint(
            ["project_id"], ["ticketing.projects.project_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["location_code"], ["ticketing.locations.location_code"], ondelete="CASCADE"
        ),
        schema="ticketing",
    )

    # ── 4. Alter ticketing.officer_scopes ─────────────────────────────────────
    op.add_column("officer_scopes",
                  sa.Column("includes_children", sa.Boolean, nullable=False, server_default="false"),
                  schema="ticketing")
    op.add_column("officer_scopes",
                  sa.Column("project_id", sa.String(64), nullable=True),
                  schema="ticketing")
    op.create_foreign_key(
        "officer_scopes_project_id_fkey",
        "officer_scopes", "projects",
        ["project_id"], ["project_id"],
        source_schema="ticketing", referent_schema="ticketing",
        ondelete="SET NULL",
    )

    # ── 5. Alter ticketing.tickets ────────────────────────────────────────────
    op.add_column("tickets",
                  sa.Column("project_id", sa.String(64), nullable=True),
                  schema="ticketing")
    op.create_foreign_key(
        "tickets_project_id_fkey",
        "tickets", "projects",
        ["project_id"], ["project_id"],
        source_schema="ticketing", referent_schema="ticketing",
        ondelete="SET NULL",
    )
    op.create_index("idx_tickets_project_id", "tickets", ["project_id"], schema="ticketing")

    # ── 6. Ensure required organizations exist, then seed KL_ROAD project ────
    # Keep this migration self-contained for fresh environments where
    # ticketing.organizations may exist but not yet contain DOR/ADB rows.
    op.execute("""
        INSERT INTO ticketing.organizations
            (organization_id, name, country_code, is_active, created_at, updated_at)
        VALUES
            ('DOR', 'Department of Roads (DOR)', 'NP', true, NOW(), NOW()),
            ('ADB', 'Asian Development Bank (ADB)', 'NP', true, NOW(), NOW())
        ON CONFLICT (organization_id) DO UPDATE SET
            name = EXCLUDED.name,
            updated_at = NOW();
    """)

    op.execute(f"""
        INSERT INTO ticketing.projects
            (project_id, country_code, short_code, name, description, is_active, created_at, updated_at)
        VALUES
            ('{KL_ROAD_PROJECT_ID}', 'NP', 'KL_ROAD',
             'Kakarbhitta-Laukahi Road (KL Road)',
             'ADB Loan 52097-003 — Nepal Province 1 road infrastructure project',
             true, NOW(), NOW())
        ON CONFLICT DO NOTHING;
    """)

    # Link KL_ROAD to both organizations
    op.execute(f"""
        INSERT INTO ticketing.project_organizations (project_id, organization_id)
        VALUES
            ('{KL_ROAD_PROJECT_ID}', 'DOR'),
            ('{KL_ROAD_PROJECT_ID}', 'ADB')
        ON CONFLICT DO NOTHING;
    """)

    # Link KL_ROAD to the 3 districts that exist in the locations table
    op.execute(f"""
        INSERT INTO ticketing.project_locations (project_id, location_code)
        SELECT '{KL_ROAD_PROJECT_ID}', location_code
        FROM ticketing.locations
        WHERE location_code IN ('JHAPA', 'MORANG', 'SUNSARI')
        ON CONFLICT DO NOTHING;
    """)

    # ── 7. Backfill tickets.project_id from project_code ─────────────────────
    op.execute(f"""
        UPDATE ticketing.tickets
        SET project_id = '{KL_ROAD_PROJECT_ID}'
        WHERE project_code = 'KL_ROAD';
    """)


def downgrade() -> None:
    op.drop_index("idx_tickets_project_id", table_name="tickets", schema="ticketing")
    op.drop_constraint("tickets_project_id_fkey", "tickets", schema="ticketing", type_="foreignkey")
    op.drop_column("tickets", "project_id", schema="ticketing")

    op.drop_constraint("officer_scopes_project_id_fkey", "officer_scopes", schema="ticketing", type_="foreignkey")
    op.drop_column("officer_scopes", "project_id",        schema="ticketing")
    op.drop_column("officer_scopes", "includes_children", schema="ticketing")

    op.drop_table("project_locations",    schema="ticketing")
    op.drop_table("project_organizations", schema="ticketing")
    op.drop_index("idx_projects_short_code", table_name="projects", schema="ticketing")
    op.drop_index("idx_projects_country",    table_name="projects", schema="ticketing")
    op.drop_table("projects", schema="ticketing")
