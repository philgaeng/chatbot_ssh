# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""Replace project_workflows.intake_routes[] with scalar intake_route (story_main).

Revision ID: e7f9a1b3
Revises: d6f8a0b2
"""
from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa

revision = "e7f9a1b3"
down_revision = "d6f8a0b2"
branch_labels = None
depends_on = None


def _route_from_legacy_array(raw: str) -> str | None:
    text = (raw or "").lower()
    if "seah_intake" in text or '"seah"' in text:
        return "seah_intake"
    if any(
        k in text
        for k in (
            "road_hazard_grievance",
            "dust_grievance",
            "fast_track",
            '"road_hazard"',
            '"dust"',
        )
    ):
        return "road_hazard_grievance"
    if any(
        k in text
        for k in ("new_grievance", "grievance_new", "standard_grievance")
    ):
        return "new_grievance"
    return None


def upgrade() -> None:
    op.add_column(
        "project_workflows",
        sa.Column("intake_route", sa.String(64), nullable=True),
        schema="ticketing",
    )

    op.execute(
        """
        UPDATE ticketing.project_workflows
        SET intake_route = NULL
        WHERE is_default = true
        """
    )

    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            """
            SELECT project_workflow_id, intake_routes::text AS routes
            FROM ticketing.project_workflows
            WHERE is_default = false
            """
        )
    ).fetchall()
    for pw_id, routes in rows:
        route = _route_from_legacy_array(routes or "")
        if route:
            conn.execute(
                sa.text(
                    """
                    UPDATE ticketing.project_workflows
                    SET intake_route = :route
                    WHERE project_workflow_id = :id
                    """
                ),
                {"route": route, "id": pw_id},
            )

    # Label-based fallback for rows still null.
    op.execute(
        """
        UPDATE ticketing.project_workflows
        SET intake_route = 'seah_intake'
        WHERE is_default = false
          AND intake_route IS NULL
          AND display_label ILIKE '%seah%'
        """
    )
    op.execute(
        """
        UPDATE ticketing.project_workflows
        SET intake_route = 'road_hazard_grievance'
        WHERE is_default = false
          AND intake_route IS NULL
          AND display_label ILIKE '%road%'
        """
    )
    op.execute(
        """
        UPDATE ticketing.project_workflows
        SET intake_route = 'new_grievance'
        WHERE is_default = false
          AND intake_route IS NULL
        """
    )

    op.drop_column("project_workflows", "intake_routes", schema="ticketing")

    # Normalize project_types.workflow_bindings JSON templates.
    type_rows = conn.execute(
        sa.text(
            "SELECT type_key, workflow_bindings::text FROM ticketing.project_types"
        )
    ).fetchall()
    for type_key, bindings_text in type_rows:
        bindings = json.loads(bindings_text or "[]")
        if not isinstance(bindings, list):
            continue
        updated: list[dict] = []
        for item in bindings:
            if not isinstance(item, dict):
                continue
            row = dict(item)
            routes = row.pop("intake_routes", None)
            if row.get("is_default"):
                row["intake_route"] = None
            elif row.get("intake_route"):
                pass
            elif routes:
                row["intake_route"] = _route_from_legacy_array(json.dumps(routes))
            else:
                label = (row.get("display_label") or "").lower()
                if "seah" in label:
                    row["intake_route"] = "seah_intake"
                elif "road" in label:
                    row["intake_route"] = "road_hazard_grievance"
                else:
                    row["intake_route"] = "new_grievance"
            updated.append(row)
        conn.execute(
            sa.text(
                """
                UPDATE ticketing.project_types
                SET workflow_bindings = CAST(:bindings AS jsonb)
                WHERE type_key = :type_key
                """
            ),
            {
                "bindings": json.dumps(updated),
                "type_key": type_key,
            },
        )


def downgrade() -> None:
    op.add_column(
        "project_workflows",
        sa.Column("intake_routes", sa.JSON(), nullable=False, server_default="[]"),
        schema="ticketing",
    )
    op.execute(
        """
        UPDATE ticketing.project_workflows
        SET intake_routes = CASE intake_route
            WHEN 'seah_intake' THEN '["seah_intake"]'::jsonb
            WHEN 'road_hazard_grievance' THEN '["road_hazard_grievance"]'::jsonb
            WHEN 'new_grievance' THEN '["new_grievance"]'::jsonb
            ELSE '[]'::jsonb
        END
        WHERE intake_route IS NOT NULL
        """
    )
    op.drop_column("project_workflows", "intake_route", schema="ticketing")
