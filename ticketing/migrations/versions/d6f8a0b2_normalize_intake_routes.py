# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""Normalize project_workflows.intake_routes to active catalog keys.

Revision ID: d6f8a0b2
Revises: c5e7f9a1
"""
from __future__ import annotations

from alembic import op

revision = "d6f8a0b2"
down_revision = "c5e7f9a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Safeguards / default rows: legacy standard/new_grievance → grievance_new only.
    op.execute(
        """
        UPDATE ticketing.project_workflows
        SET intake_routes = '["grievance_new"]'::jsonb
        WHERE is_default = true
           OR intake_routes::text LIKE '%standard_grievance%'
           OR intake_routes::text LIKE '%new_grievance%'
        """
    )
    # Road hazard rows: drop legacy dust key.
    op.execute(
        """
        UPDATE ticketing.project_workflows
        SET intake_routes = '["fast_track", "road_hazard"]'::jsonb
        WHERE intake_routes::text LIKE '%road_hazard%'
           OR intake_routes::text LIKE '%fast_track%'
           OR intake_routes::text LIKE '%dust%'
        """
    )
    # project_types.workflow_bindings normalized at read time via API; optional manual re-save in UI.


def downgrade() -> None:
    pass
