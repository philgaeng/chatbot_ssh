# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""admin_scopes table; role_kind and role_origin on roles

Revision ID: a2b4c6d8
Revises: z1a3b5c7
Create Date: 2026-06-08
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a2b4c6d8"
down_revision: Union[str, None] = "z1a3b5c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ADMIN_ROLE_KEYS = ("super_admin", "country_admin", "project_admin")


def upgrade() -> None:
    op.create_table(
        "admin_scopes",
        sa.Column("admin_scope_id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("role_key", sa.String(64), nullable=False),
        sa.Column("country_code", sa.String(8), nullable=True),
        sa.Column("project_id", sa.String(64), nullable=True),
        sa.Column("organization_id", sa.String(64), nullable=True),
        sa.Column("package_id", sa.String(64), nullable=True),
        sa.Column("workflow_track", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by_user_id", sa.String(128), nullable=True),
        schema="ticketing",
    )
    op.create_index(
        "idx_admin_scopes_user",
        "admin_scopes",
        ["user_id"],
        schema="ticketing",
    )
    op.create_index(
        "idx_admin_scopes_project",
        "admin_scopes",
        ["project_id"],
        schema="ticketing",
    )
    op.create_index(
        "idx_admin_scopes_country_track",
        "admin_scopes",
        ["country_code", "workflow_track"],
        schema="ticketing",
    )

    op.add_column(
        "roles",
        sa.Column("role_kind", sa.String(16), nullable=True),
        schema="ticketing",
    )
    op.add_column(
        "roles",
        sa.Column("role_origin", sa.String(16), nullable=False, server_default="system"),
        schema="ticketing",
    )

    conn = op.get_bind()
    admin_keys_sql = ", ".join(f"'{k}'" for k in ADMIN_ROLE_KEYS)
    conn.execute(
        sa.text(
            f"""
            UPDATE ticketing.roles
            SET role_kind = CASE
                WHEN role_key IN ({admin_keys_sql}) THEN 'admin'
                ELSE 'operational'
            END,
            role_origin = 'system'
            """
        )
    )
    conn.execute(
        sa.text(
            """
            UPDATE ticketing.roles
            SET role_kind = 'operational'
            WHERE role_kind IS NULL
            """
        )
    )
    op.alter_column(
        "roles",
        "role_kind",
        existing_type=sa.String(16),
        nullable=False,
        schema="ticketing",
    )


def downgrade() -> None:
    op.drop_column("roles", "role_origin", schema="ticketing")
    op.drop_column("roles", "role_kind", schema="ticketing")
    op.drop_index("idx_admin_scopes_country_track", table_name="admin_scopes", schema="ticketing")
    op.drop_index("idx_admin_scopes_project", table_name="admin_scopes", schema="ticketing")
    op.drop_index("idx_admin_scopes_user", table_name="admin_scopes", schema="ticketing")
    op.drop_table("admin_scopes", schema="ticketing")
