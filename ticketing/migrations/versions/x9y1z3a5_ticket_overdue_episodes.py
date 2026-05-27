# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""add ticket_overdue_episodes and tickets.current_overdue_episode_id

Revision ID: x9y1z3a5
Revises: w8x0y2z4
Create Date: 2026-05-26
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "x9y1z3a5"
down_revision: Union[str, None] = "w8x0y2z4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ticket_overdue_episodes",
        sa.Column("episode_id", sa.String(36), primary_key=True),
        sa.Column(
            "ticket_id",
            sa.String(36),
            sa.ForeignKey("ticketing.tickets.ticket_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workflow_step_id",
            sa.String(36),
            sa.ForeignKey("ticketing.workflow_steps.step_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("step_order", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("assigned_to_user_id", sa.String(128), nullable=True),
        sa.Column("assigned_role_id", sa.String(36), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_reason", sa.String(32), nullable=True),
        sa.Column("days_overdue", sa.Integer(), nullable=True),
        sa.Column("triggered_by", sa.String(32), nullable=False, server_default="SLA_WATCHDOG"),
        schema="ticketing",
    )
    op.create_index(
        "idx_overdue_episodes_ticket_started",
        "ticket_overdue_episodes",
        ["ticket_id", "started_at"],
        schema="ticketing",
    )
    op.create_index(
        "idx_overdue_episodes_ticket_ended",
        "ticket_overdue_episodes",
        ["ticket_id", "ended_at"],
        schema="ticketing",
    )
    op.add_column(
        "tickets",
        sa.Column("current_overdue_episode_id", sa.String(36), nullable=True),
        schema="ticketing",
    )
    op.create_foreign_key(
        "fk_tickets_current_overdue_episode",
        "tickets",
        "ticket_overdue_episodes",
        ["current_overdue_episode_id"],
        ["episode_id"],
        source_schema="ticketing",
        referent_schema="ticketing",
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_tickets_current_overdue_episode",
        "tickets",
        schema="ticketing",
        type_="foreignkey",
    )
    op.drop_column("tickets", "current_overdue_episode_id", schema="ticketing")
    op.drop_index(
        "idx_overdue_episodes_ticket_ended",
        table_name="ticket_overdue_episodes",
        schema="ticketing",
    )
    op.drop_index(
        "idx_overdue_episodes_ticket_started",
        table_name="ticket_overdue_episodes",
        schema="ticketing",
    )
    op.drop_table("ticket_overdue_episodes", schema="ticketing")
