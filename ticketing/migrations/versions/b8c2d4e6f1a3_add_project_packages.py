"""add project_packages, package_locations, officer_scopes.package_id + seed KL Road lots

Revision ID: b8c2d4e6f1a3
Revises: a9c3e5f1d720
Create Date: 2026-04-24

Safe to run: only creates ticketing.project_packages / ticketing.package_locations,
adds package_id column to ticketing.officer_scopes.
Does NOT touch: grievances, complainants, or any existing public.* table.

KL Road (short_code='KL_ROAD') packages are seeded if the project already exists.
The seed is idempotent — safe to re-run.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision      = "b8c2d4e6f1a3"
down_revision = "a9c3e5f1d720"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    # ── 1. Create ticketing.project_packages ─────────────────────────────────
    op.create_table(
        "project_packages",
        sa.Column("package_id",        sa.String(36),  nullable=False),
        sa.Column("project_id",        sa.String(64),  nullable=False),
        sa.Column("package_code",      sa.String(128), nullable=False),
        sa.Column("name",              sa.Text(),       nullable=False),
        sa.Column("description",       sa.Text(),       nullable=True),
        sa.Column("contractor_org_id", sa.String(64),  nullable=True),
        sa.Column("is_active",         sa.Boolean(),   nullable=False, server_default="true"),
        sa.Column("created_at",        sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at",        sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("package_id"),
        sa.UniqueConstraint("project_id", "package_code", name="uq_project_packages_code"),
        sa.ForeignKeyConstraint(
            ["project_id"], ["ticketing.projects.project_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["contractor_org_id"], ["ticketing.organizations.organization_id"],
            ondelete="SET NULL",
        ),
        schema="ticketing",
    )
    op.create_index("idx_project_packages_project",    "project_packages", ["project_id"],        schema="ticketing")
    op.create_index("idx_project_packages_contractor", "project_packages", ["contractor_org_id"], schema="ticketing")

    # ── 2. Create ticketing.package_locations ─────────────────────────────────
    op.create_table(
        "package_locations",
        sa.Column("package_id",    sa.String(36), nullable=False),
        sa.Column("location_code", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("package_id", "location_code"),
        sa.ForeignKeyConstraint(
            ["package_id"], ["ticketing.project_packages.package_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["location_code"], ["ticketing.locations.location_code"],
            ondelete="CASCADE",
        ),
        schema="ticketing",
    )
    op.create_index("idx_package_locations_location", "package_locations", ["location_code"], schema="ticketing")

    # ── 3. Add package_id column to officer_scopes ────────────────────────────
    op.add_column(
        "officer_scopes",
        sa.Column(
            "package_id", sa.String(36), nullable=True,
            comment="When set, officer is scoped to this civil-works package only",
        ),
        schema="ticketing",
    )
    op.create_foreign_key(
        "fk_officer_scopes_package_id",
        source_table="officer_scopes",
        referent_table="project_packages",
        local_cols=["package_id"],
        remote_cols=["package_id"],
        source_schema="ticketing",
        referent_schema="ticketing",
        ondelete="SET NULL",
    )
    op.create_index("idx_officer_scopes_package", "officer_scopes", ["package_id"], schema="ticketing")

    # ── 4. Seed 5 KL Road packages (only if KL_ROAD project exists) ──────────
    #
    # District location assignments (Province 1 corridor):
    #   Lot 1  Km  0–45   Jhapa (NP_D004)
    #   Lot 2  Km 45–85   Morang (NP_D006)
    #   Lot 3  Km 85–95.76  Sunsari (NP_D011)
    #   Lot 4  Bridges: Ninda, Biring, Kankai  →  Jhapa (NP_D004)
    #   Lot 5  Bridges: Ratuwa, Bakra, Lohendra →  Jhapa (NP_D004) + Morang (NP_D006)
    #
    op.execute(sa.text("""
        INSERT INTO ticketing.project_packages
            (package_id, project_id, package_code, name, description, is_active, created_at, updated_at)
        SELECT
            gen_random_uuid(),
            p.project_id,
            v.package_code,
            v.name,
            v.description,
            true,
            NOW(),
            NOW()
        FROM ticketing.projects p
        CROSS JOIN (VALUES
            ('SHEP/OCB/KL/01',   'Lot 1 — Kakarbhitta to Sitapur',              'Civil works: Km 0+000 to Km 45+000'),
            ('SHEP/OCB/KL/02',   'Lot 2 — Km 45 to Km 85',                      'Civil works: Km 45+000 to Km 85+000'),
            ('SHEP/OCB/KL/03',   'Lot 3 — Km 85 to Km 95.76',                   'Civil works: Km 85+000 to Km 95+760'),
            ('SHEP/OCB/MBKL/04', 'Lot 4 — Major Bridges (Ninda, Biring, Kankai)', 'Bridge construction: Ninda, Biring, Kankai rivers'),
            ('SHEP/OCB/MBKL/05', 'Lot 5 — Major Bridges (Ratuwa, Bakra, Lohendra)', 'Bridge construction: Ratuwa, Bakra, Lohendra rivers')
        ) AS v(package_code, name, description)
        WHERE p.short_code = 'KL_ROAD'
        ON CONFLICT (project_id, package_code) DO NOTHING
    """))

    op.execute(sa.text("""
        INSERT INTO ticketing.package_locations (package_id, location_code)
        SELECT pp.package_id, v.location_code
        FROM ticketing.project_packages pp
        JOIN ticketing.projects p ON p.project_id = pp.project_id
        CROSS JOIN (VALUES
            ('SHEP/OCB/KL/01',   'NP_D004'),
            ('SHEP/OCB/KL/02',   'NP_D006'),
            ('SHEP/OCB/KL/03',   'NP_D011'),
            ('SHEP/OCB/MBKL/04', 'NP_D004'),
            ('SHEP/OCB/MBKL/05', 'NP_D004'),
            ('SHEP/OCB/MBKL/05', 'NP_D006')
        ) AS v(package_code, location_code)
        WHERE p.short_code = 'KL_ROAD'
          AND pp.package_code = v.package_code
          AND EXISTS (
              SELECT 1 FROM ticketing.locations
              WHERE location_code = v.location_code
          )
        ON CONFLICT DO NOTHING
    """))


def downgrade() -> None:
    op.drop_index("idx_officer_scopes_package", table_name="officer_scopes", schema="ticketing")
    op.drop_constraint("fk_officer_scopes_package_id", "officer_scopes", schema="ticketing", type_="foreignkey")
    op.drop_column("officer_scopes", "package_id", schema="ticketing")

    op.drop_index("idx_package_locations_location", table_name="package_locations", schema="ticketing")
    op.drop_table("package_locations", schema="ticketing")

    op.drop_index("idx_project_packages_contractor", table_name="project_packages", schema="ticketing")
    op.drop_index("idx_project_packages_project",    table_name="project_packages", schema="ticketing")
    op.drop_table("project_packages", schema="ticketing")
