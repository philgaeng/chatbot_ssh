# Safe to run: only creates/modifies ops.* objects
# Does NOT touch: grievances, complainants, public.* or ticketing.* tables
"""ops.dependency_findings (CVE / advisory tracking)

Revision ID: ops002_depfindings
Revises: ops001_init
Create Date: 2026-06-23
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "ops002_depfindings"
down_revision: Union[str, None] = "ops001_init"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dependency_findings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("package", sa.Text(), nullable=False),
        sa.Column("installed_ver", sa.Text(), nullable=True),
        sa.Column("advisory_id", sa.String(length=128), nullable=True),
        sa.Column("severity", sa.String(length=16), nullable=True),
        sa.Column("fixed_in", sa.Text(), nullable=True),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("source", "package", "advisory_id", name="uq_dep_finding"),
        schema="ops",
    )
    # ops_app r/w is covered by ALTER DEFAULT PRIVILEGES from ops001 (same migration role).


def downgrade() -> None:
    op.drop_table("dependency_findings", schema="ops")
