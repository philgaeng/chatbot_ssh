# Safe to run: only creates ticketing.ticket_tasks
# Does NOT touch: grievances, complainants, or any public.* table
#
# Adds in-thread task assignment table for the mobile-first UI.
# Tasks fire TASK_ASSIGNED / TASK_COMPLETED events into ticket_events
# so they appear in the case thread (docs/claude-tickets/UI_SPEC.md §2.5).

from alembic import op
import sqlalchemy as sa

revision = "f2b4d6e8a0c3"
down_revision = "e5a7b2c089d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ticket_tasks",
        sa.Column("task_id", sa.String(36), primary_key=True),
        sa.Column("ticket_id", sa.String(36), sa.ForeignKey("ticketing.tickets.ticket_id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_type", sa.String(32), nullable=False),
        sa.Column("assigned_to_user_id", sa.String(128), nullable=False),
        sa.Column("assigned_by_user_id", sa.String(128), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_by_user_id", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="ticketing",
    )
    op.create_index("idx_ticket_tasks_ticket_id", "ticket_tasks", ["ticket_id"], schema="ticketing")
    op.create_index("idx_ticket_tasks_assigned_to", "ticket_tasks", ["assigned_to_user_id", "status"], schema="ticketing")


def downgrade() -> None:
    op.drop_index("idx_ticket_tasks_assigned_to", table_name="ticket_tasks", schema="ticketing")
    op.drop_index("idx_ticket_tasks_ticket_id", table_name="ticket_tasks", schema="ticketing")
    op.drop_table("ticket_tasks", schema="ticketing")
