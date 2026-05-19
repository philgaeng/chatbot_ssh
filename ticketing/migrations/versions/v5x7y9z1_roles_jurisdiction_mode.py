# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table

"""add ticketing.roles.jurisdiction_mode (field | country | global)

Revision ID: v5x7y9z1
Revises: u3v5w7x9
Create Date: 2026-05-19
"""

from alembic import op
import sqlalchemy as sa

revision = "v5x7y9z1"
down_revision = "u3v5w7x9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "roles",
        sa.Column("jurisdiction_mode", sa.String(16), nullable=True),
        schema="ticketing",
    )
    op.execute(
        """
        UPDATE ticketing.roles SET jurisdiction_mode = 'global'
        WHERE role_key = 'super_admin';
        UPDATE ticketing.roles SET jurisdiction_mode = 'country'
        WHERE role_key IN (
            'country_admin',
            'adb_national_project_director',
            'adb_hq_safeguards',
            'adb_hq_project',
            'adb_hq_exec'
        );
        UPDATE ticketing.roles SET jurisdiction_mode = 'field'
        WHERE jurisdiction_mode IS NULL;
        """
    )


def downgrade() -> None:
    op.drop_column("roles", "jurisdiction_mode", schema="ticketing")
