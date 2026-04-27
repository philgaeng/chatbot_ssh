# Safe to run: only adds two nullable columns to ticketing.tickets
# Does NOT touch: grievances, complainants, or any existing public.* table
"""add ai_summary_en and ai_summary_updated_at to ticketing.tickets

Revision ID: c1d5f8a2e047
Revises: b8c2d4e6f1a3
Create Date: 2026-04-27 00:00:00.000000

Adds two columns needed by the LLM findings feature (TODO item 7b):
  - ai_summary_en         TEXT         — AI-generated case findings paragraph (English)
  - ai_summary_updated_at TIMESTAMPTZ  — when the summary was last generated

Both are nullable — existing rows get NULL, which the frontend treats as "not yet generated".
translation_en for per-note translation goes into the existing TicketEvent.payload JSONB
(no migration needed for that).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c1d5f8a2e047"
down_revision = "b8c2d4e6f1a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tickets",
        sa.Column("ai_summary_en", sa.Text(), nullable=True),
        schema="ticketing",
    )
    op.add_column(
        "tickets",
        sa.Column(
            "ai_summary_updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        schema="ticketing",
    )


def downgrade() -> None:
    op.drop_column("tickets", "ai_summary_updated_at", schema="ticketing")
    op.drop_column("tickets", "ai_summary_en", schema="ticketing")
