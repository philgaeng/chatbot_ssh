# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""Enforce one active ticket per grievance_id (HR-03).

Pre-flight dedups any grievance_id that already has >1 non-deleted ticket
(keep oldest by created_at, soft-delete the rest + SYSTEM event on the survivor),
then replaces the non-unique idx_tickets_grievance_id with a partial UNIQUE index
scoped to is_deleted = false.

Revision ID: h2j4l6n8
Revises: g0h2i4j6
Create Date: 2026-07-05
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "h2j4l6n8"
down_revision: Union[str, None] = "g0h2i4j6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

_UNIQUE_INDEX = "uq_tickets_grievance_id_active"
_OLD_INDEX = "idx_tickets_grievance_id"


def _dedup_active_tickets(bind) -> None:
    """Keep the oldest non-deleted ticket per grievance_id; soft-delete the rest.

    Expected to be a no-op in practice — the invariant has held via the
    application-level guard — but the migration must still handle it so the
    UNIQUE index can be created without violation.
    """
    dup_groups = bind.execute(
        sa.text(
            """
            SELECT grievance_id
            FROM ticketing.tickets
            WHERE is_deleted = false
            GROUP BY grievance_id
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()

    total_soft_deleted = 0
    for (grievance_id,) in dup_groups:
        rows = bind.execute(
            sa.text(
                """
                SELECT ticket_id, is_seah
                FROM ticketing.tickets
                WHERE grievance_id = :gid AND is_deleted = false
                ORDER BY created_at ASC, ticket_id ASC
                """
            ),
            {"gid": grievance_id},
        ).fetchall()

        survivor_id, survivor_is_seah = rows[0][0], rows[0][1]
        loser_ids = [r[0] for r in rows[1:]]

        bind.execute(
            sa.text(
                """
                UPDATE ticketing.tickets
                SET is_deleted = true, updated_at = now()
                WHERE ticket_id = ANY(:ids)
                """
            ),
            {"ids": loser_ids},
        )
        total_soft_deleted += len(loser_ids)

        bind.execute(
            sa.text(
                """
                INSERT INTO ticketing.ticket_events
                    (event_id, ticket_id, event_type, note, payload, seen,
                     created_by_user_id, created_at, case_sensitivity,
                     summary_regen_required)
                VALUES
                    (:eid, :tid, 'SYSTEM', :note, CAST(:payload AS json), true,
                     'system', now(), :cs, false)
                """
            ),
            {
                "eid": str(uuid.uuid4()),
                "tid": survivor_id,
                "note": (
                    f"Merged {len(loser_ids)} duplicate ticket(s) for "
                    f"grievance_id={grievance_id} while enforcing the unique "
                    f"active-ticket index (HR-03)."
                ),
                "payload": json.dumps(
                    {
                        "reason": "hr03_unique_index_dedup",
                        "grievance_id": grievance_id,
                        "survivor_ticket_id": survivor_id,
                        "soft_deleted_ticket_ids": loser_ids,
                    }
                ),
                "cs": "seah" if survivor_is_seah else "standard",
            },
        )

    logger.info(
        "HR-03 dedup: %d grievance_id(s) had duplicates, %d ticket(s) soft-deleted",
        len(dup_groups),
        total_soft_deleted,
    )


def upgrade() -> None:
    _dedup_active_tickets(op.get_bind())

    # Partial UNIQUE index: one active (non-deleted) ticket per grievance_id.
    op.create_index(
        _UNIQUE_INDEX,
        "tickets",
        ["grievance_id"],
        unique=True,
        schema="ticketing",
        postgresql_where=sa.text("is_deleted = false"),
    )
    # Drop the old non-unique index — the unique partial index covers the same lookups.
    op.drop_index(_OLD_INDEX, table_name="tickets", schema="ticketing")


def downgrade() -> None:
    op.create_index(
        _OLD_INDEX,
        "tickets",
        ["grievance_id"],
        schema="ticketing",
    )
    op.drop_index(_UNIQUE_INDEX, table_name="tickets", schema="ticketing")
