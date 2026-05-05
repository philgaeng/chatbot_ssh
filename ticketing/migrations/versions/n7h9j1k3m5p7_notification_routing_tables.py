# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""notification_routes: country + optional project SMS/email provider routing

Revision ID: n7h9j1k3m5p7
Revises: h5e7g9i1k3m5
Create Date: 2026-05-04

Stores non-PII policy for which outbound provider (sns, ses, noop, local_*, …)
and template ids apply per country default or per-project override.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "n7h9j1k3m5p7"
down_revision: Union[str, None] = "h5e7g9i1k3m5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification_routes",
        sa.Column("route_id", sa.String(length=36), nullable=False),
        sa.Column("country_code", sa.String(length=8), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=True),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("provider_key", sa.String(length=32), nullable=False),
        sa.Column("template_id", sa.String(length=128), nullable=True),
        sa.Column("secondary_template_id", sa.String(length=128), nullable=True),
        sa.Column("options_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["country_code"],
            ["ticketing.countries.country_code"],
            name="notification_routes_country_code_fkey",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["ticketing.projects.project_id"],
            name="notification_routes_project_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("route_id"),
        schema="ticketing",
    )

    op.create_index(
        "uq_notif_routes_country_channel_default",
        "notification_routes",
        ["country_code", "channel"],
        unique=True,
        schema="ticketing",
        postgresql_where=sa.text("project_id IS NULL"),
    )
    op.create_index(
        "uq_notif_routes_project_channel",
        "notification_routes",
        ["project_id", "channel"],
        unique=True,
        schema="ticketing",
        postgresql_where=sa.text("project_id IS NOT NULL"),
    )
    op.create_index(
        "idx_notif_routes_country_project",
        "notification_routes",
        ["country_code", "project_id", "channel", "is_active"],
        schema="ticketing",
    )

    # Seed defaults for Nepal when country exists (matches current AWS-first stack).
    op.execute(
        """
        INSERT INTO ticketing.notification_routes (
            route_id, country_code, project_id, channel, provider_key,
            template_id, secondary_template_id, options_json, is_active, notes
        )
        SELECT gen_random_uuid()::text, 'NP', NULL, 'sms', 'sns',
               NULL, NULL, NULL, true,
               'Default from migration n7h9j1k3m5p7; edit via admin / notifications UI.'
        WHERE EXISTS (SELECT 1 FROM ticketing.countries c WHERE c.country_code = 'NP')
          AND NOT EXISTS (
              SELECT 1 FROM ticketing.notification_routes r
              WHERE r.country_code = 'NP' AND r.project_id IS NULL AND r.channel = 'sms'
          );
        """
    )
    op.execute(
        """
        INSERT INTO ticketing.notification_routes (
            route_id, country_code, project_id, channel, provider_key,
            template_id, secondary_template_id, options_json, is_active, notes
        )
        SELECT gen_random_uuid()::text, 'NP', NULL, 'email', 'ses',
               NULL, NULL, NULL, true,
               'Default from migration n7h9j1k3m5p7; edit via admin / notifications UI.'
        WHERE EXISTS (SELECT 1 FROM ticketing.countries c WHERE c.country_code = 'NP')
          AND NOT EXISTS (
              SELECT 1 FROM ticketing.notification_routes r
              WHERE r.country_code = 'NP' AND r.project_id IS NULL AND r.channel = 'email'
          );
        """
    )


def downgrade() -> None:
    op.drop_index("idx_notif_routes_country_project", table_name="notification_routes", schema="ticketing")
    op.drop_index(
        "uq_notif_routes_project_channel",
        table_name="notification_routes",
        schema="ticketing",
    )
    op.drop_index(
        "uq_notif_routes_country_channel_default",
        table_name="notification_routes",
        schema="ticketing",
    )
    op.drop_table("notification_routes", schema="ticketing")
