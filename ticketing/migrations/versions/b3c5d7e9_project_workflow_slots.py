# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""N workflow slots per project (safeguards, hazards, CA, SEAH, custom).

Revision ID: b3c5d7e9
Revises: a2b4c6d8
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "b3c5d7e9"
down_revision = "a2b4c6d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_workflows",
        sa.Column("project_workflow_id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(64), nullable=False),
        sa.Column("slot_key", sa.String(64), nullable=False),
        sa.Column("workflow_id", sa.String(36), nullable=False),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["ticketing.projects.project_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["ticketing.workflow_definitions.workflow_id"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("project_id", "slot_key", name="uq_project_workflows_project_slot"),
        schema="ticketing",
    )
    op.create_index(
        "idx_project_workflows_project",
        "project_workflows",
        ["project_id"],
        schema="ticketing",
    )

    # Backfill from legacy columns.
    op.execute(
        """
        INSERT INTO ticketing.project_workflows (
            project_workflow_id, project_id, slot_key, workflow_id, sort_order
        )
        SELECT
            gen_random_uuid()::text,
            project_id,
            'safeguards',
            standard_workflow_id,
            10
        FROM ticketing.projects
        WHERE standard_workflow_id IS NOT NULL
        """
    )
    op.execute(
        """
        INSERT INTO ticketing.project_workflows (
            project_workflow_id, project_id, slot_key, workflow_id, sort_order
        )
        SELECT
            gen_random_uuid()::text,
            project_id,
            'seah',
            seah_workflow_id,
            40
        FROM ticketing.projects
        WHERE seah_workflow_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("idx_project_workflows_project", table_name="project_workflows", schema="ticketing")
    op.drop_table("project_workflows", schema="ticketing")
