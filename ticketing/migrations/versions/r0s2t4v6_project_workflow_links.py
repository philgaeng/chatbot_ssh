# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""Link standard and SEAH workflows on ticketing.projects.

Revision ID: r0s2t4v6
Revises: q9r7s1u3
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "r0s2t4v6"
down_revision = "q9r7s1u3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("standard_workflow_id", sa.String(36), nullable=True),
        schema="ticketing",
    )
    op.add_column(
        "projects",
        sa.Column("seah_workflow_id", sa.String(36), nullable=True),
        schema="ticketing",
    )
    op.create_foreign_key(
        "fk_projects_standard_workflow",
        "projects",
        "workflow_definitions",
        ["standard_workflow_id"],
        ["workflow_id"],
        source_schema="ticketing",
        referent_schema="ticketing",
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_projects_seah_workflow",
        "projects",
        "workflow_definitions",
        ["seah_workflow_id"],
        ["workflow_id"],
        source_schema="ticketing",
        referent_schema="ticketing",
        ondelete="SET NULL",
    )

    # Backfill KL Road demo project from known seed workflow IDs.
    op.execute(
        """
        UPDATE ticketing.projects
        SET standard_workflow_id = '00000000-0000-0000-0001-000000000001'
        WHERE short_code = 'KL_ROAD'
          AND standard_workflow_id IS NULL
          AND EXISTS (
            SELECT 1 FROM ticketing.workflow_definitions
            WHERE workflow_id = '00000000-0000-0000-0001-000000000001'
          )
        """
    )
    op.execute(
        """
        UPDATE ticketing.projects
        SET seah_workflow_id = '00000000-0000-0000-0002-000000000001'
        WHERE short_code = 'KL_ROAD'
          AND seah_workflow_id IS NULL
          AND EXISTS (
            SELECT 1 FROM ticketing.workflow_definitions
            WHERE workflow_id = '00000000-0000-0000-0002-000000000001'
          )
        """
    )


def downgrade() -> None:
    op.drop_constraint("fk_projects_seah_workflow", "projects", schema="ticketing", type_="foreignkey")
    op.drop_constraint("fk_projects_standard_workflow", "projects", schema="ticketing", type_="foreignkey")
    op.drop_column("projects", "seah_workflow_id", schema="ticketing")
    op.drop_column("projects", "standard_workflow_id", schema="ticketing")
