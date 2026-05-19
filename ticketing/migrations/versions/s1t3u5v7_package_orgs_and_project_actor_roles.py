# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""package_organizations, project_actor_roles; drop contractor_org_id

Revision ID: s1t3u5v7
Revises: r0s2t4v6
"""
from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa

revision = "s1t3u5v7"
down_revision = "r0s2t4v6"
branch_labels = None
depends_on = None

DEFAULT_ORG_ROLES = [
    {"key": "project_owner", "label": "Project Owner", "description": "Government agency that owns and executes the project (e.g. DOR)"},
    {"key": "donor", "label": "Donor / Lender", "description": "Multilateral or bilateral financing institution (e.g. ADB)"},
    {"key": "executing_agency", "label": "Executing Agency", "description": "Central ministry or agency responsible for project oversight"},
    {"key": "implementing_agency", "label": "Implementing Agency", "description": "PD/PIU or other unit responsible for day-to-day implementation"},
    {"key": "main_contractor", "label": "Main Contractor", "description": "Primary civil works contractor"},
    {"key": "subcontractor_t1", "label": "Subcontractor (Tier 1)", "description": "First-tier subcontractor to the main contractor"},
    {"key": "subcontractor_t2", "label": "Subcontractor (Tier 2)", "description": "Second-tier subcontractor"},
    {"key": "supervision_consultant", "label": "CSC – Construction Supervision Consultant", "description": "Independent consultant supervising construction quality"},
    {"key": "specialized_consultant", "label": "Specialized Consultant", "description": "Safeguards, environment, social, or other specialist consultant"},
]


def upgrade() -> None:
    op.create_table(
        "project_actor_roles",
        sa.Column("project_id", sa.String(64), nullable=False),
        sa.Column("role_key", sa.String(64), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["project_id"], ["ticketing.projects.project_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("project_id", "role_key"),
        schema="ticketing",
    )

    conn = op.get_bind()
    roles_row = conn.execute(
        sa.text("SELECT value FROM ticketing.settings WHERE key = 'org_roles'")
    ).fetchone()
    if roles_row and roles_row[0]:
        source_roles = roles_row[0] if isinstance(roles_row[0], list) else DEFAULT_ORG_ROLES
    else:
        source_roles = DEFAULT_ORG_ROLES

    projects = conn.execute(sa.text("SELECT project_id FROM ticketing.projects")).fetchall()
    for (project_id,) in projects:
        for i, entry in enumerate(source_roles):
            key = entry.get("key") or ""
            label = entry.get("label") or key
            desc = entry.get("description") or ""
            if not key:
                continue
            conn.execute(
                sa.text(
                    """
                    INSERT INTO ticketing.project_actor_roles
                        (project_id, role_key, label, description, sort_order)
                    VALUES (:project_id, :role_key, :label, :description, :sort_order)
                    ON CONFLICT DO NOTHING
                    """
                ),
                {
                    "project_id": project_id,
                    "role_key": key,
                    "label": label,
                    "description": desc or None,
                    "sort_order": i,
                },
            )

    op.create_table(
        "package_organizations",
        sa.Column("package_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(64), nullable=False),
        sa.Column("org_role", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["package_id"], ["ticketing.project_packages.package_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["ticketing.organizations.organization_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("package_id", "organization_id", "org_role"),
        schema="ticketing",
    )
    op.create_index(
        "idx_package_organizations_org",
        "package_organizations",
        ["organization_id"],
        schema="ticketing",
    )

    conn.execute(
        sa.text(
            """
            INSERT INTO ticketing.package_organizations (package_id, organization_id, org_role)
            SELECT package_id, contractor_org_id, 'main_contractor'
            FROM ticketing.project_packages
            WHERE contractor_org_id IS NOT NULL
            """
        )
    )

    op.drop_index("idx_project_packages_contractor", table_name="project_packages", schema="ticketing")
    op.drop_constraint(
        "project_packages_contractor_org_id_fkey",
        "project_packages",
        schema="ticketing",
        type_="foreignkey",
    )
    op.drop_column("project_packages", "contractor_org_id", schema="ticketing")


def downgrade() -> None:
    op.add_column(
        "project_packages",
        sa.Column("contractor_org_id", sa.String(64), nullable=True),
        schema="ticketing",
    )
    op.create_foreign_key(
        "project_packages_contractor_org_id_fkey",
        "project_packages",
        "organizations",
        ["contractor_org_id"],
        ["organization_id"],
        source_schema="ticketing",
        referent_schema="ticketing",
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_project_packages_contractor",
        "project_packages",
        ["contractor_org_id"],
        schema="ticketing",
    )

    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE ticketing.project_packages pp
            SET contractor_org_id = po.organization_id
            FROM ticketing.package_organizations po
            WHERE po.package_id = pp.package_id
              AND po.org_role = 'main_contractor'
            """
        )
    )

    op.drop_index("idx_package_organizations_org", table_name="package_organizations", schema="ticketing")
    op.drop_table("package_organizations", schema="ticketing")
    op.drop_table("project_actor_roles", schema="ticketing")
