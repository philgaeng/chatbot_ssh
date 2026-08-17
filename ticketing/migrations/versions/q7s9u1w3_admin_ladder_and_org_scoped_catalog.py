# SPDX-License-Identifier: Apache-2.0

# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""SH-7 — 4-tier admin ladder + org-scoped catalog (doc 11 §2, §3.3).

Two things:
  1. Retire `country_admin` → `org_admin` (doc 11 §2.4): rename the catalog role row
     (role_id preserved, so user_roles FKs are intact) and the string role_key on
     admin_scopes. Add the new narrowest tier `officer_admin` to the catalog (the seed
     fills its full definition; this INSERT just guarantees existing DBs have the row).
     Legacy country_admin rows kept their `country_code` and (usually NULL)
     `organization_id`; a NULL-org org_admin reads as "whole tree on its track" — no
     invented org anchor (see admin_access.admin_org_scope_ids).
  2. Org-scoped catalog (doc 11 §3.3): add `owner_organization_id` to `roles` and
     `workflow_definitions` (mirrors position_types from OC-02). NULL = global/super-owned.

Revision ID: q7s9u1w3
Revises: o5q7s9u1
Create Date: 2026-07-11
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "q7s9u1w3"
down_revision: Union[str, None] = "o5q7s9u1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CATALOG_TABLES = ("roles", "workflow_definitions")


def upgrade() -> None:
    # ── org-scoped catalog columns ──
    for table in _CATALOG_TABLES:
        op.add_column(
            table,
            sa.Column("owner_organization_id", sa.String(length=64), nullable=True),
            schema="ticketing",
        )
        op.create_foreign_key(
            f"fk_{table}_owner_org",
            table,
            "organizations",
            ["owner_organization_id"],
            ["organization_id"],
            source_schema="ticketing",
            referent_schema="ticketing",
            ondelete="SET NULL",
        )
        op.create_index(
            f"idx_{table}_owner_org", table, ["owner_organization_id"], schema="ticketing"
        )

    # ── retire country_admin → org_admin ──
    op.execute(
        "UPDATE ticketing.admin_scopes SET role_key = 'org_admin' WHERE role_key = 'country_admin'"
    )
    # role_id is preserved by the rename, so user_roles.role_id FKs stay valid.
    op.execute(
        "UPDATE ticketing.roles SET role_key = 'org_admin', "
        "display_name = 'Organization Admin' WHERE role_key = 'country_admin'"
    )

    # ── add the officer_admin admin role if absent (seed fills the full definition) ──
    op.execute(
        """
        INSERT INTO ticketing.roles
            (role_id, role_key, display_name, description, workflow_scope,
             jurisdiction_mode, permissions, role_kind, role_origin, created_at, updated_at)
        SELECT gen_random_uuid()::text, 'officer_admin', 'Officer Admin',
               'Invite, modify, and revoke officers only, within scope.', 'Both',
               'field', '[]'::json, 'admin', 'system', now(), now()
        WHERE NOT EXISTS (SELECT 1 FROM ticketing.roles WHERE role_key = 'officer_admin')
        """
    )


def downgrade() -> None:
    # Best-effort inverse: fails only if officer_admin has been assigned (FK) — fine for a
    # fresh up→down→up check where it is unused.
    op.execute(
        "DELETE FROM ticketing.roles WHERE role_key = 'officer_admin' AND role_origin = 'system'"
    )
    op.execute(
        "UPDATE ticketing.roles SET role_key = 'country_admin', "
        "display_name = 'Country Admin' WHERE role_key = 'org_admin'"
    )
    op.execute(
        "UPDATE ticketing.admin_scopes SET role_key = 'country_admin' WHERE role_key = 'org_admin'"
    )
    for table in reversed(_CATALOG_TABLES):
        op.drop_index(f"idx_{table}_owner_org", table_name=table, schema="ticketing")
        op.drop_constraint(f"fk_{table}_owner_org", table, schema="ticketing", type_="foreignkey")
        op.drop_column(table, "owner_organization_id", schema="ticketing")
