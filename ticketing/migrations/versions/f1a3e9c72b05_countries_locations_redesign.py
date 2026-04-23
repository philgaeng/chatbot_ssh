"""countries, location tree redesign, location translations, org country FK

Revision ID: f1a3e9c72b05
Revises: d5f3e1a09c28
Create Date: 2026-04-23

# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
#
# Changes:
#   CREATE  ticketing.countries
#   CREATE  ticketing.location_level_defs
#   CREATE  ticketing.location_translations
#   ALTER   ticketing.locations
#             - rename parent_location → parent_location_code
#             - add level_number, source_id, is_active
#             - add FK country_code → countries
#             - drop organization_id column (organizations do not belong on a location node)
#             - drop name column (names moved to location_translations)
#   ALTER   ticketing.organizations
#             - make country_code nullable + add FK → countries
#   DATA    seed Nepal country + level defs + English translations for existing location rows
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "f1a3e9c72b05"
down_revision = "d5f3e1a09c28"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. countries ──────────────────────────────────────────────────────────
    op.create_table(
        "countries",
        sa.Column("country_code", sa.String(8),  nullable=False),
        sa.Column("name",         sa.Text,        nullable=False),
        sa.Column("created_at",   sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at",   sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("country_code"),
        schema="ticketing",
    )

    # ── 2. location_level_defs ───────────────────────────────────────────────
    op.create_table(
        "location_level_defs",
        sa.Column("country_code",    sa.String(8),  nullable=False),
        sa.Column("level_number",    sa.Integer,    nullable=False),
        sa.Column("level_name_en",   sa.Text,       nullable=False),
        sa.Column("level_name_local",sa.Text,       nullable=True),
        sa.PrimaryKeyConstraint("country_code", "level_number"),
        sa.ForeignKeyConstraint(
            ["country_code"], ["ticketing.countries.country_code"], ondelete="CASCADE"
        ),
        schema="ticketing",
    )

    # ── 3. location_translations ─────────────────────────────────────────────
    op.create_table(
        "location_translations",
        sa.Column("location_code", sa.String(64), nullable=False),
        sa.Column("lang_code",     sa.String(8),  nullable=False),
        sa.Column("name",          sa.Text,       nullable=False),
        sa.PrimaryKeyConstraint("location_code", "lang_code"),
        sa.ForeignKeyConstraint(
            ["location_code"], ["ticketing.locations.location_code"], ondelete="CASCADE"
        ),
        schema="ticketing",
    )

    # ── 4. Alter ticketing.locations ─────────────────────────────────────────

    # 4a. Drop FK on organization_id (must drop constraint before column)
    op.drop_constraint(
        "locations_organization_id_fkey", "locations", schema="ticketing", type_="foreignkey"
    )
    # 4b. Drop FK on parent_location so we can rename it
    op.drop_constraint(
        "locations_parent_location_fkey", "locations", schema="ticketing", type_="foreignkey"
    )

    # 4c. Add new columns
    op.add_column("locations", sa.Column("level_number", sa.Integer, nullable=True), schema="ticketing")
    op.add_column("locations", sa.Column("source_id",    sa.Integer, nullable=True), schema="ticketing")
    op.add_column("locations", sa.Column("is_active",    sa.Boolean, nullable=True), schema="ticketing")

    # 4d. Rename parent_location → parent_location_code
    op.alter_column("locations", "parent_location", new_column_name="parent_location_code", schema="ticketing")

    # 4e. Data: set level_number and is_active from existing hierarchy
    #     Nodes with no parent = level 1; nodes with a parent = level 2
    op.execute("""
        UPDATE ticketing.locations SET is_active = true;
        UPDATE ticketing.locations SET level_number = 1 WHERE parent_location_code IS NULL;
        UPDATE ticketing.locations SET level_number = 2 WHERE parent_location_code IS NOT NULL;
    """)

    # 4f. Make level_number and is_active NOT NULL now that data is set
    op.alter_column("locations", "level_number", nullable=False, schema="ticketing")
    op.alter_column("locations", "is_active",    nullable=False, schema="ticketing")

    # 4g. Re-add self-FK with new column name
    op.create_foreign_key(
        "locations_parent_location_code_fkey",
        "locations", "locations",
        ["parent_location_code"], ["location_code"],
        source_schema="ticketing", referent_schema="ticketing",
        ondelete="SET NULL",
    )

    # 4h. Drop organization_id column
    op.drop_column("locations", "organization_id", schema="ticketing")

    # 4i. Add indexes
    op.create_index("idx_locations_country_level", "locations",
                    ["country_code", "level_number"], schema="ticketing")
    op.create_index("idx_locations_parent", "locations",
                    ["parent_location_code"], schema="ticketing")

    # ── 5. Alter ticketing.organizations: make country_code nullable + add FK ──
    op.alter_column("organizations", "country_code", nullable=True, schema="ticketing")
    op.create_foreign_key(
        "organizations_country_code_fkey",
        "organizations", "countries",
        ["country_code"], ["country_code"],
        source_schema="ticketing", referent_schema="ticketing",
        ondelete="SET NULL",
    )

    # ── 6. Seed data ─────────────────────────────────────────────────────────

    # Nepal country
    op.execute("""
        INSERT INTO ticketing.countries (country_code, name, created_at, updated_at)
        VALUES ('NP', 'Nepal', NOW(), NOW())
        ON CONFLICT DO NOTHING;
    """)

    # Nepal admin level definitions
    op.execute("""
        INSERT INTO ticketing.location_level_defs
            (country_code, level_number, level_name_en, level_name_local)
        VALUES
            ('NP', 1, 'Province',     'प्रदेश'),
            ('NP', 2, 'District',     'जिल्ला'),
            ('NP', 3, 'Municipality', 'नगरपालिका')
        ON CONFLICT DO NOTHING;
    """)

    # Add FK from locations to countries (data already has country_code = 'NP')
    op.create_foreign_key(
        "locations_country_code_fkey",
        "locations", "countries",
        ["country_code"], ["country_code"],
        source_schema="ticketing", referent_schema="ticketing",
        ondelete="RESTRICT",
    )

    # Seed English translations for the 4 existing location rows
    op.execute("""
        INSERT INTO ticketing.location_translations (location_code, lang_code, name)
        SELECT location_code, 'en', name FROM ticketing.locations
        ON CONFLICT DO NOTHING;
    """)

    # Drop the name column from locations (names now live in location_translations)
    op.drop_column("locations", "name", schema="ticketing")


def downgrade() -> None:
    # Re-add name column with placeholder
    op.add_column("locations",
                  sa.Column("name", sa.Text, nullable=True),
                  schema="ticketing")
    op.execute("""
        UPDATE ticketing.locations l
        SET name = COALESCE(
            (SELECT lt.name FROM ticketing.location_translations lt
             WHERE lt.location_code = l.location_code AND lt.lang_code = 'en' LIMIT 1),
            l.location_code
        )
    """)
    op.alter_column("locations", "name", nullable=False, schema="ticketing")

    op.drop_constraint("locations_country_code_fkey",  "locations",    schema="ticketing", type_="foreignkey")
    op.drop_constraint("organizations_country_code_fkey", "organizations", schema="ticketing", type_="foreignkey")
    op.alter_column("organizations", "country_code", nullable=False, schema="ticketing")

    op.drop_index("idx_locations_country_level", table_name="locations", schema="ticketing")
    op.drop_index("idx_locations_parent",        table_name="locations", schema="ticketing")
    op.drop_constraint("locations_parent_location_code_fkey", "locations", schema="ticketing", type_="foreignkey")
    op.alter_column("locations", "parent_location_code", new_column_name="parent_location", schema="ticketing")
    op.create_foreign_key(
        "locations_parent_location_fkey", "locations", "locations",
        ["parent_location"], ["location_code"],
        source_schema="ticketing", referent_schema="ticketing", ondelete="SET NULL",
    )
    op.drop_column("locations", "is_active",    schema="ticketing")
    op.drop_column("locations", "source_id",    schema="ticketing")
    op.drop_column("locations", "level_number", schema="ticketing")

    op.add_column("locations",
                  sa.Column("organization_id", sa.String(64), nullable=True),
                  schema="ticketing")
    op.create_foreign_key(
        "locations_organization_id_fkey", "locations", "organizations",
        ["organization_id"], ["organization_id"],
        source_schema="ticketing", referent_schema="ticketing", ondelete="SET NULL",
    )

    op.drop_table("location_translations", schema="ticketing")
    op.drop_table("location_level_defs",   schema="ticketing")
    op.drop_table("countries",             schema="ticketing")
