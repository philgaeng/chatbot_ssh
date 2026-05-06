# Safe to run: only creates ticketing.ticket_viewers
# Does NOT touch: grievances, complainants, or any public.* table
#
# Adds case viewers/watchers table (UI_SPEC.md §2.7).
# Viewers can read the case thread and post notes.

from alembic import op
import sqlalchemy as sa

revision = "g4d6f8b0c2e5"
down_revision = "f2b4d6e8a0c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ticket_viewers",
        sa.Column("viewer_id", sa.String(36), primary_key=True),
        sa.Column("ticket_id", sa.String(36),
                  sa.ForeignKey("ticketing.tickets.ticket_id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("added_by_user_id", sa.String(128), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("ticket_id", "user_id", name="uq_ticket_viewers_ticket_user"),
        schema="ticketing",
    )
    op.create_index("idx_ticket_viewers_ticket_id", "ticket_viewers", ["ticket_id"], schema="ticketing")
    op.create_index("idx_ticket_viewers_user_id", "ticket_viewers", ["user_id"], schema="ticketing")


def downgrade() -> None:
    op.drop_index("idx_ticket_viewers_user_id", table_name="ticket_viewers", schema="ticketing")
    op.drop_index("idx_ticket_viewers_ticket_id", table_name="ticket_viewers", schema="ticketing")
    op.drop_table("ticket_viewers", schema="ticketing")
