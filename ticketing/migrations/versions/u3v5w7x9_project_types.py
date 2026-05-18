# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""project_types archetypes; projects.project_type_key; seed construction_road

Revision ID: u3v5w7x9
Revises: s1t3u5v7
"""
from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa

revision = "u3v5w7x9"
down_revision = "s1t3u5v7"
branch_labels = None
depends_on = None

STANDARD_WF = "00000000-0000-0000-0001-000000000001"
SEAH_WF = "00000000-0000-0000-0002-000000000001"

CONSTRUCTION_ROAD_ACTOR_ROLES = [
    {
        "key": "implementing_agency",
        "label": "Implementing Agency",
        "description": "PD/PIU or other unit responsible for day-to-day implementation",
        "required": True,
        "required_package": False,
        "scope": "project",
    },
    {
        "key": "donor",
        "label": "Donor / Lender",
        "description": "Multilateral or bilateral financing institution (e.g. ADB)",
        "required": True,
        "required_package": False,
        "scope": "project",
    },
    {
        "key": "main_contractor",
        "label": "Main Contractor",
        "description": "Primary civil works contractor (project-wide or per package)",
        "required": False,
        "required_package": True,
        "scope": "both",
    },
    {
        "key": "supervision_consultant",
        "label": "CSC – Construction Supervision Consultant",
        "description": "Independent consultant supervising construction quality",
        "required": False,
        "required_package": False,
        "scope": "project",
    },
]


def upgrade() -> None:
    op.create_table(
        "project_types",
        sa.Column("type_key", sa.String(64), primary_key=True),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("standard_workflow_id", sa.String(36), nullable=True),
        sa.Column("seah_workflow_id", sa.String(36), nullable=True),
        sa.Column("routing_org_role", sa.String(64), nullable=False, server_default="implementing_agency"),
        sa.Column("actor_roles", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema="ticketing",
    )
    op.create_foreign_key(
        "fk_project_types_standard_workflow",
        "project_types",
        "workflow_definitions",
        ["standard_workflow_id"],
        ["workflow_id"],
        source_schema="ticketing",
        referent_schema="ticketing",
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_project_types_seah_workflow",
        "project_types",
        "workflow_definitions",
        ["seah_workflow_id"],
        ["workflow_id"],
        source_schema="ticketing",
        referent_schema="ticketing",
        ondelete="SET NULL",
    )

    op.add_column(
        "projects",
        sa.Column("project_type_key", sa.String(64), nullable=True),
        schema="ticketing",
    )
    op.create_foreign_key(
        "fk_projects_project_type",
        "projects",
        "project_types",
        ["project_type_key"],
        ["type_key"],
        source_schema="ticketing",
        referent_schema="ticketing",
        ondelete="SET NULL",
    )

    roles_json = json.dumps(CONSTRUCTION_ROAD_ACTOR_ROLES)
    op.execute(
        f"""
        INSERT INTO ticketing.project_types (
            type_key, label, description,
            standard_workflow_id, seah_workflow_id,
            routing_org_role, actor_roles, is_active, sort_order
        )
        SELECT
            'construction_road',
            'Construction (road)',
            'Road or civil-works corridor with packages, contractors, and standard + SEAH workflows.',
            '{STANDARD_WF}',
            '{SEAH_WF}',
            'implementing_agency',
            '{roles_json}'::jsonb,
            true,
            0
        WHERE EXISTS (
            SELECT 1 FROM ticketing.workflow_definitions
            WHERE workflow_id = '{STANDARD_WF}'
        )
        ON CONFLICT (type_key) DO NOTHING
        """
    )

    op.execute(
        """
        UPDATE ticketing.projects
        SET project_type_key = 'construction_road'
        WHERE short_code = 'KL_ROAD'
          AND project_type_key IS NULL
          AND EXISTS (
            SELECT 1 FROM ticketing.project_types WHERE type_key = 'construction_road'
          )
        """
    )


def downgrade() -> None:
    op.drop_constraint("fk_projects_project_type", "projects", schema="ticketing", type_="foreignkey")
    op.drop_column("projects", "project_type_key", schema="ticketing")
    op.drop_constraint("fk_project_types_seah_workflow", "project_types", schema="ticketing", type_="foreignkey")
    op.drop_constraint("fk_project_types_standard_workflow", "project_types", schema="ticketing", type_="foreignkey")
    op.drop_table("project_types", schema="ticketing")
