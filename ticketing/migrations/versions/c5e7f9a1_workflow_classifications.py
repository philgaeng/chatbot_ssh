# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""Dynamic project workflows: classifications, intake routes, default flag.

Revision ID: c5e7f9a1
Revises: c4d6e8f0
"""
from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa

revision = "c5e7f9a1"
down_revision = "c4d6e8f0"
branch_labels = None
depends_on = None

STANDARD_WF = "00000000-0000-0000-0001-000000000001"
SEAH_WF = "00000000-0000-0000-0002-000000000001"

ROAD_HAZARD_CLS = json.dumps(["Road Hazard"])
SEAH_CLS = json.dumps(
    ["Gender", "Gender, Social", "Malicious Behavior", "Malicious Behavior, Environmental"]
)
ROAD_INTAKE = json.dumps(["fast_track", "road_hazard", "dust"])
SEAH_INTAKE = json.dumps(["seah_intake"])
SAFEGUARDS_INTAKE = json.dumps(["standard_grievance", "grievance_new", "new_grievance"])


def upgrade() -> None:
    op.add_column(
        "project_workflows",
        sa.Column("display_label", sa.Text(), nullable=True),
        schema="ticketing",
    )
    op.add_column(
        "project_workflows",
        sa.Column("classifications", sa.JSON(), nullable=False, server_default="[]"),
        schema="ticketing",
    )
    op.add_column(
        "project_workflows",
        sa.Column("intake_routes", sa.JSON(), nullable=False, server_default="[]"),
        schema="ticketing",
    )
    op.add_column(
        "project_workflows",
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        schema="ticketing",
    )

    op.add_column(
        "project_types",
        sa.Column("workflow_bindings", sa.JSON(), nullable=False, server_default="[]"),
        schema="ticketing",
    )

    op.add_column(
        "tickets",
        sa.Column("intake_route", sa.String(64), nullable=True),
        schema="ticketing",
    )
    op.add_column(
        "tickets",
        sa.Column("intake_fast_path", sa.String(64), nullable=True),
        schema="ticketing",
    )

    # Migrate legacy slot_key rows → new shape (3 streams: Safeguards, Road hazard, SEAH).
    op.execute(
        f"""
        UPDATE ticketing.project_workflows
        SET display_label = 'Safeguards GRM',
            is_default = true,
            classifications = '[]'::jsonb,
            intake_routes = '{SAFEGUARDS_INTAKE}'::jsonb
        WHERE slot_key = 'safeguards'
        """
    )
    op.execute(
        f"""
        UPDATE ticketing.project_workflows
        SET display_label = 'Road hazard',
            is_default = false,
            classifications = '{ROAD_HAZARD_CLS}'::jsonb,
            intake_routes = '{ROAD_INTAKE}'::jsonb
        WHERE slot_key = 'hazards'
        """
    )
    op.execute(
        f"""
        UPDATE ticketing.project_workflows
        SET display_label = 'SEAH',
            is_default = false,
            classifications = '{SEAH_CLS}'::jsonb,
            intake_routes = '{SEAH_INTAKE}'::jsonb
        WHERE slot_key = 'seah'
        """
    )
    op.execute("DELETE FROM ticketing.project_workflows WHERE slot_key = 'ca'")

    # Ensure Road hazard binding exists on projects that already have Safeguards only.
    op.execute(
        f"""
        INSERT INTO ticketing.project_workflows (
            project_workflow_id, project_id, slot_key, workflow_id,
            display_label, sort_order, is_default, classifications, intake_routes
        )
        SELECT
            gen_random_uuid()::text,
            p.project_id,
            'hazards',
            COALESCE(p.standard_workflow_id, pw.workflow_id),
            'Road hazard',
            20,
            false,
            '{ROAD_HAZARD_CLS}'::jsonb,
            '{ROAD_INTAKE}'::jsonb
        FROM ticketing.projects p
        LEFT JOIN ticketing.project_workflows pw
          ON pw.project_id = p.project_id AND pw.is_default = true
        WHERE COALESCE(p.standard_workflow_id, pw.workflow_id) IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM ticketing.project_workflows x
            WHERE x.project_id = p.project_id
              AND (x.display_label = 'Road hazard' OR x.slot_key = 'hazards')
          )
        """
    )

    # Projects with only legacy columns (no project_workflows rows yet).
    op.execute(
        f"""
        INSERT INTO ticketing.project_workflows (
            project_workflow_id, project_id, slot_key, workflow_id,
            display_label, sort_order, is_default, classifications, intake_routes
        )
        SELECT
            gen_random_uuid()::text,
            p.project_id,
            'safeguards',
            p.standard_workflow_id,
            'Safeguards GRM',
            10,
            true,
            '[]'::jsonb,
            '{SAFEGUARDS_INTAKE}'::jsonb
        FROM ticketing.projects p
        WHERE p.standard_workflow_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM ticketing.project_workflows pw
            WHERE pw.project_id = p.project_id
          )
        """
    )
    op.execute(
        f"""
        INSERT INTO ticketing.project_workflows (
            project_workflow_id, project_id, slot_key, workflow_id,
            display_label, sort_order, is_default, classifications, intake_routes
        )
        SELECT
            gen_random_uuid()::text,
            p.project_id,
            'hazards',
            p.standard_workflow_id,
            'Road hazard',
            20,
            false,
            '{ROAD_HAZARD_CLS}'::jsonb,
            '{ROAD_INTAKE}'::jsonb
        FROM ticketing.projects p
        WHERE p.standard_workflow_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM ticketing.project_workflows pw
            WHERE pw.project_id = p.project_id AND pw.display_label = 'Road hazard'
          )
        """
    )
    op.execute(
        f"""
        INSERT INTO ticketing.project_workflows (
            project_workflow_id, project_id, slot_key, workflow_id,
            display_label, sort_order, is_default, classifications, intake_routes
        )
        SELECT
            gen_random_uuid()::text,
            p.project_id,
            'seah',
            p.seah_workflow_id,
            'SEAH',
            30,
            false,
            '{SEAH_CLS}'::jsonb,
            '{SEAH_INTAKE}'::jsonb
        FROM ticketing.projects p
        WHERE p.seah_workflow_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM ticketing.project_workflows pw
            WHERE pw.project_id = p.project_id AND pw.workflow_id = p.seah_workflow_id
          )
        """
    )

    op.execute(
        """
        UPDATE ticketing.project_workflows
        SET display_label = COALESCE(display_label, slot_key)
        WHERE display_label IS NULL
        """
    )
    op.alter_column(
        "project_workflows",
        "display_label",
        nullable=False,
        schema="ticketing",
    )

    seed_bindings = json.dumps(
        [
            {
                "display_label": "Safeguards GRM",
                "workflow_id": STANDARD_WF,
                "is_default": True,
                "classifications": [],
                "intake_routes": json.loads(SAFEGUARDS_INTAKE),
                "sort_order": 10,
            },
            {
                "display_label": "Road hazard",
                "workflow_id": STANDARD_WF,
                "is_default": False,
                "classifications": json.loads(ROAD_HAZARD_CLS),
                "intake_routes": json.loads(ROAD_INTAKE),
                "sort_order": 20,
            },
            {
                "display_label": "SEAH",
                "workflow_id": SEAH_WF,
                "is_default": False,
                "classifications": json.loads(SEAH_CLS),
                "intake_routes": json.loads(SEAH_INTAKE),
                "sort_order": 30,
            },
        ]
    ).replace("'", "''")

    op.execute(
        f"""
        UPDATE ticketing.project_types
        SET workflow_bindings = '{seed_bindings}'::jsonb
        WHERE type_key = 'construction_road'
        """
    )

    op.drop_constraint(
        "uq_project_workflows_project_slot",
        "project_workflows",
        schema="ticketing",
        type_="unique",
    )
    op.drop_column("project_workflows", "slot_key", schema="ticketing")


def downgrade() -> None:
    op.add_column(
        "project_workflows",
        sa.Column("slot_key", sa.String(64), nullable=True),
        schema="ticketing",
    )
    op.execute(
        """
        UPDATE ticketing.project_workflows
        SET slot_key = CASE
            WHEN is_default THEN 'safeguards'
            WHEN display_label ILIKE '%road%' THEN 'hazards'
            WHEN display_label ILIKE '%seah%' THEN 'seah'
            ELSE 'custom_' || left(project_workflow_id, 8)
        END
        """
    )
    op.alter_column("project_workflows", "slot_key", nullable=False, schema="ticketing")
    op.create_unique_constraint(
        "uq_project_workflows_project_slot",
        "project_workflows",
        ["project_id", "slot_key"],
        schema="ticketing",
    )
    op.drop_column("tickets", "intake_fast_path", schema="ticketing")
    op.drop_column("tickets", "intake_route", schema="ticketing")
    op.drop_column("project_types", "workflow_bindings", schema="ticketing")
    op.drop_column("project_workflows", "is_default", schema="ticketing")
    op.drop_column("project_workflows", "intake_routes", schema="ticketing")
    op.drop_column("project_workflows", "classifications", schema="ticketing")
    op.drop_column("project_workflows", "display_label", schema="ticketing")
