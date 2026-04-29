# Safe to run: only adds columns to ticketing.ticket_events
# Does NOT touch: grievances, complainants, or any public.* table
#
# Adds three fields required by the SEAH privacy handoff spec
# (docs/claude-tickets/seah-privacy-worktree-handoff.md):
#
#   actor_role          — role key of the event creator, snapshotted at write time.
#                         Needed for role-highlighted timeline bubbles and for
#                         deterministic audit correlation with the public/chatbot
#                         audit stream (which also logs actor_role per doc 06).
#
#   case_sensitivity    — 'standard' or 'seah', copied from ticket.is_seah at event
#                         creation time. Allows audit queries to filter by sensitivity
#                         without joining back to ticketing.tickets.
#
#   summary_regen_required — signals the async LLM summary pipeline that derived
#                            summary content is stale and must be regenerated before
#                            the next officer view. Set to True on status changes,
#                            escalations, and note additions per doc 05.

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "e5a7b2c089d1"
down_revision = "d2e8f4a1b093"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ticket_events",
        sa.Column("actor_role", sa.String(64), nullable=True),
        schema="ticketing",
    )
    op.add_column(
        "ticket_events",
        sa.Column(
            "case_sensitivity",
            sa.String(16),
            nullable=False,
            server_default="standard",
        ),
        schema="ticketing",
    )
    op.add_column(
        "ticket_events",
        sa.Column(
            "summary_regen_required",
            sa.Boolean,
            nullable=False,
            server_default=sa.false(),
        ),
        schema="ticketing",
    )
    # Index for the async summary worker: quickly find events that need regen
    op.create_index(
        "idx_ticket_events_regen",
        "ticket_events",
        ["summary_regen_required", "created_at"],
        schema="ticketing",
    )


def downgrade() -> None:
    op.drop_index("idx_ticket_events_regen", table_name="ticket_events", schema="ticketing")
    op.drop_column("ticket_events", "summary_regen_required", schema="ticketing")
    op.drop_column("ticket_events", "case_sensitivity", schema="ticketing")
    op.drop_column("ticket_events", "actor_role", schema="ticketing")
