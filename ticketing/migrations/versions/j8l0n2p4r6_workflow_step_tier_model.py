# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""workflow step tier model — supervisor_role, observer_roles, informed_roles, informed_pii_access

Implements spec 12 (notification model + admin role split):
  - WorkflowStep: add supervisor_role, observer_roles, informed_roles, informed_pii_access
  - Roles: add country_admin and project_admin (replaces local_admin)
  - Settings: seed default notification_rules for standard + SEAH workflows
  - Backfill supervisor_role on existing KL Road Standard + SEAH seed steps

Revision ID: j8l0n2p4r6
Revises: i6j8l0n2p4
Create Date: 2026-05-05
"""
from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "j8l0n2p4r6"
down_revision: Union[str, None] = "i6j8l0n2p4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── Default notification rules (stored in ticketing.settings) ─────────────────

_DEFAULT_NOTIFICATION_RULES = {
    "standard": {
        "ticket_created":   {"actor": ["app", "email"], "supervisor": ["app", "email"], "informed": [],              "observer": []},
        "ticket_escalated": {"actor": ["app", "email"], "supervisor": ["app", "email"], "informed": ["email"],       "observer": []},
        "ticket_resolved":  {"actor": ["app", "email"], "supervisor": ["app"],          "informed": [],              "observer": []},
        "sla_breach":       {"actor": ["app", "email"], "supervisor": ["app", "email"], "informed": ["email"],       "observer": []},
        "grc_convened":     {"actor": ["app", "email"], "supervisor": ["app"],          "informed": ["app"],         "observer": []},
        "assignment":       {"actor": ["sms", "app"],   "supervisor": [],               "informed": [],              "observer": []},
        "quarterly_report": {"actor": [],               "supervisor": ["email"],        "informed": ["email"],       "observer": []},
    },
    "seah": {
        "ticket_created":   {"actor": ["app", "email"], "supervisor": ["app", "email"], "informed": [],              "observer": []},
        "ticket_escalated": {"actor": ["app"],          "supervisor": ["app"],          "informed": [],              "observer": []},
        "ticket_resolved":  {"actor": ["app"],          "supervisor": ["app"],          "informed": [],              "observer": []},
        "sla_breach":       {"actor": ["app", "email"], "supervisor": ["app", "email"], "informed": [],              "observer": []},
        "assignment":       {"actor": ["app"],          "supervisor": [],               "informed": [],              "observer": []},
    },
}

_DEFAULT_COMPLAINANT_NOTIFICATIONS = {
    "ticket_created":     {"chatbot": True, "sms_fallback": True},
    "ticket_acknowledged": {"chatbot": True, "sms_fallback": True},
    "ticket_resolved":    {"chatbot": True, "sms_fallback": True},
    "reply_sent":         {"chatbot": True, "sms_fallback": True},
}

# Stable step IDs matching kl_road_standard.py / kl_road_seah.py seed
_STEP_SUPERVISORS = {
    # Standard GRM
    "00000000-0000-0000-0001-000000000011": "pd_piu_safeguards_focal",      # L1
    "00000000-0000-0000-0001-000000000012": "adb_national_project_director", # L2
    "00000000-0000-0000-0001-000000000013": "adb_hq_safeguards",             # L3
    "00000000-0000-0000-0001-000000000014": None,                             # L4 — no supervisor
    # SEAH
    "00000000-0000-0000-0002-000000000011": "seah_hq_officer",               # SEAH L1
    "00000000-0000-0000-0002-000000000012": "adb_hq_exec",                   # SEAH L2
}

# GRC members are standing Informed at L3
_STEP_INFORMED_ROLES = {
    "00000000-0000-0000-0001-000000000013": ["grc_member"],  # L3 GRC step
}


def upgrade() -> None:
    # ── 1. Add new columns to workflow_steps ─────────────────────────────────
    op.add_column(
        "workflow_steps",
        sa.Column("supervisor_role", sa.String(64), nullable=True),
        schema="ticketing",
    )
    op.add_column(
        "workflow_steps",
        sa.Column(
            "observer_roles",
            sa.JSON,
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
        schema="ticketing",
    )
    op.add_column(
        "workflow_steps",
        sa.Column(
            "informed_roles",
            sa.JSON,
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
        schema="ticketing",
    )
    op.add_column(
        "workflow_steps",
        sa.Column(
            "informed_pii_access",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        schema="ticketing",
    )

    # ── 2. Backfill supervisor_role on existing seed steps ───────────────────
    conn = op.get_bind()
    for step_id, supervisor in _STEP_SUPERVISORS.items():
        if supervisor is not None:
            conn.execute(
                sa.text(
                    "UPDATE ticketing.workflow_steps "
                    "SET supervisor_role = :supervisor "
                    "WHERE step_id = :step_id"
                ),
                {"supervisor": supervisor, "step_id": step_id},
            )

    # ── 3. Backfill informed_roles on existing seed steps ────────────────────
    for step_id, roles in _STEP_INFORMED_ROLES.items():
        conn.execute(
            sa.text(
                "UPDATE ticketing.workflow_steps "
                "SET informed_roles = CAST(:roles AS json) "
                "WHERE step_id = :step_id"
            ),
            {"roles": json.dumps(roles), "step_id": step_id},
        )

    # ── 4. Add country_admin + project_admin roles ───────────────────────────
    import uuid

    new_roles = [
        {
            "role_id": str(uuid.uuid4()),
            "role_key": "country_admin",
            "display_name": "Country Administrator",
            "permissions": json.dumps([
                "tickets:read",
                "projects:manage",
                "locations:manage",
                "workflows:manage",
                "users:invite",
                "settings:write",
            ]),
        },
        {
            "role_id": str(uuid.uuid4()),
            "role_key": "project_admin",
            "display_name": "Project Administrator",
            "permissions": json.dumps([
                "tickets:read",
                "officers:assign",
                "notifications:configure",
                "settings:project",
            ]),
        },
    ]
    for role in new_roles:
        existing = conn.execute(
            sa.text(
                "SELECT role_id FROM ticketing.roles WHERE role_key = :key"
            ),
            {"key": role["role_key"]},
        ).fetchone()
        if not existing:
            conn.execute(
                sa.text(
                    "INSERT INTO ticketing.roles "
                    "(role_id, role_key, display_name, permissions, created_at, updated_at) "
                    "VALUES (:role_id, :role_key, :display_name, CAST(:permissions AS json), NOW(), NOW())"
                ),
                role,
            )

    # ── 5. Seed default notification_rules + complainant_notifications ────────
    settings_rows = [
        ("notification_rules",          json.dumps(_DEFAULT_NOTIFICATION_RULES)),
        ("complainant_notifications",   json.dumps(_DEFAULT_COMPLAINANT_NOTIFICATIONS)),
    ]
    for key, value in settings_rows:
        existing = conn.execute(
            sa.text("SELECT key FROM ticketing.settings WHERE key = :key"),
            {"key": key},
        ).fetchone()
        if not existing:
            conn.execute(
                sa.text(
                    "INSERT INTO ticketing.settings (key, value, updated_at) "
                    "VALUES (:key, CAST(:value AS json), NOW())"
                ),
                {"key": key, "value": value},
            )


def downgrade() -> None:
    conn = op.get_bind()

    # Remove seeded settings
    conn.execute(
        sa.text("DELETE FROM ticketing.settings WHERE key IN ('notification_rules', 'complainant_notifications')")
    )

    # Remove new roles
    conn.execute(
        sa.text("DELETE FROM ticketing.roles WHERE role_key IN ('country_admin', 'project_admin')")
    )

    # Drop new columns
    op.drop_column("workflow_steps", "informed_pii_access", schema="ticketing")
    op.drop_column("workflow_steps", "informed_roles", schema="ticketing")
    op.drop_column("workflow_steps", "observer_roles", schema="ticketing")
    op.drop_column("workflow_steps", "supervisor_role", schema="ticketing")
