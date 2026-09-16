# SPDX-License-Identifier: Apache-2.0

# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""Org tree columns on ticketing.organizations (OC-01).

Turns the flat org list into a forest (doc 16 §3.1):
  - parent_organization_id  self-FK, nullable (existing flat orgs become roots)
  - org_category            government|local_government|donor|third_party
                            NOT NULL (denormalized onto every node = root's category,
                            authoritative & inherited from root). Existing rows are all
                            roots and are backfilled to 'government' (see downgrade note).
  - unit_type               fine-grained sub-type, nullable, CHECK-constrained domain
  - territory_location_code optional FK into ticketing.locations (routable office)
  - territory_includes_children  boolean, same semantics as officer_scopes.includes_children
  - display_name_ne         Nepali display name (doc 16 §10 — cheap now, painful later)

All additive on ticketing.organizations. Existing officer_scopes / tickets.organization_id
FKs are unchanged; existing orgs still resolve on tickets after upgrade.

Revision ID: m3o5q7s9
Revises: k1m3o5q7
Create Date: 2026-07-10
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "m3o5q7s9"
down_revision: Union[str, None] = "k1m3o5q7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ORG_CATEGORIES = ("government", "local_government", "donor", "third_party")
_UNIT_TYPES = (
    "ministry",
    "department",
    "directorate",
    "provincial_office",
    "division_office",
    "company",
    "development_partner",
    "province_assembly",
    "municipality",
)


def _in_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    # ── columns (org_category added nullable first, backfilled, then set NOT NULL) ──
    op.add_column(
        "organizations",
        sa.Column("parent_organization_id", sa.String(length=64), nullable=True),
        schema="ticketing",
    )
    op.add_column(
        "organizations",
        sa.Column("org_category", sa.String(length=32), nullable=True),
        schema="ticketing",
    )
    op.add_column(
        "organizations",
        sa.Column("unit_type", sa.String(length=32), nullable=True),
        schema="ticketing",
    )
    op.add_column(
        "organizations",
        sa.Column("territory_location_code", sa.String(length=64), nullable=True),
        schema="ticketing",
    )
    op.add_column(
        "organizations",
        sa.Column(
            "territory_includes_children",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        schema="ticketing",
    )
    op.add_column(
        "organizations",
        sa.Column("display_name_ne", sa.Text(), nullable=True),
        schema="ticketing",
    )

    # Existing orgs are all roots (parent NULL). org_category is NOT NULL on every node;
    # backfill roots to 'government'. NOTE: cross-country donors seeded before OC-01
    # (e.g. ADB) are mislabelled 'government' by this blanket backfill — correct them via
    # PATCH /organizations/{id} to org_category='donor'. This is a data-quality nit, not a
    # schema one: org_category only gates root-creation + org-scoped catalog (not yet live).
    op.execute(
        "UPDATE ticketing.organizations SET org_category = 'government' WHERE org_category IS NULL"
    )
    op.alter_column(
        "organizations", "org_category", nullable=False, schema="ticketing"
    )

    # ── foreign keys (explicit names so downgrade is fully reversible) ──
    op.create_foreign_key(
        "fk_organizations_parent",
        "organizations",
        "organizations",
        ["parent_organization_id"],
        ["organization_id"],
        source_schema="ticketing",
        referent_schema="ticketing",
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_organizations_territory_location",
        "organizations",
        "locations",
        ["territory_location_code"],
        ["location_code"],
        source_schema="ticketing",
        referent_schema="ticketing",
        ondelete="SET NULL",
    )

    # ── domain CHECK constraints ──
    op.create_check_constraint(
        "ck_organizations_org_category",
        "organizations",
        f"org_category IN ({_in_list(_ORG_CATEGORIES)})",
        schema="ticketing",
    )
    op.create_check_constraint(
        "ck_organizations_unit_type",
        "organizations",
        f"unit_type IS NULL OR unit_type IN ({_in_list(_UNIT_TYPES)})",
        schema="ticketing",
    )

    # ── index for subtree (descendant_org_ids) walks ──
    op.create_index(
        "idx_organizations_parent",
        "organizations",
        ["parent_organization_id"],
        schema="ticketing",
    )


def downgrade() -> None:
    op.drop_index("idx_organizations_parent", table_name="organizations", schema="ticketing")
    op.drop_constraint(
        "ck_organizations_unit_type", "organizations", schema="ticketing", type_="check"
    )
    op.drop_constraint(
        "ck_organizations_org_category", "organizations", schema="ticketing", type_="check"
    )
    op.drop_constraint(
        "fk_organizations_territory_location",
        "organizations",
        schema="ticketing",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_organizations_parent", "organizations", schema="ticketing", type_="foreignkey"
    )
    op.drop_column("organizations", "display_name_ne", schema="ticketing")
    op.drop_column("organizations", "territory_includes_children", schema="ticketing")
    op.drop_column("organizations", "territory_location_code", schema="ticketing")
    op.drop_column("organizations", "unit_type", schema="ticketing")
    op.drop_column("organizations", "org_category", schema="ticketing")
    op.drop_column("organizations", "parent_organization_id", schema="ticketing")
