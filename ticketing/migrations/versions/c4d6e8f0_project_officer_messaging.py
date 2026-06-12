# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""add officer_messaging JSON to ticketing.projects

Project-level officer SMS configuration (master toggle + per-level L1–Ln).

Revision ID: c4d6e8f0
Revises: b3c5d7e9
Create Date: 2026-06-12
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "c4d6e8f0"
down_revision: Union[str, None] = "b3c5d7e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DEFAULT = '{"sms_enabled": false, "sms_levels": [], "whatsapp_levels": []}'


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "officer_messaging",
            JSONB,
            nullable=False,
            server_default=sa.text(f"'{_DEFAULT}'::jsonb"),
        ),
        schema="ticketing",
    )


def downgrade() -> None:
    op.drop_column("projects", "officer_messaging", schema="ticketing")
