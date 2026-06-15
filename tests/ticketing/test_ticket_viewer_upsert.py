"""Ticket viewer upsert — same-transaction duplicate guard."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from ticketing.engine.escalation import _ensure_viewer
from ticketing.models.ticket_viewer import TicketViewer

from tests.ticketing.conftest import _uid

pytestmark = pytest.mark.integration


def test_ensure_viewer_twice_before_flush(ctx):
    """Duplicate (ticket_id, user_id) in one transaction must not violate unique constraint."""
    officer = _uid("officer") + "@test.grm.local"
    ticket = ctx.add_open_ticket(officer)
    v1 = _ensure_viewer(ctx.db, ticket.ticket_id, officer, "informed", "system")
    v2 = _ensure_viewer(ctx.db, ticket.ticket_id, officer, "informed", "system")
    assert v1 is v2
    ctx.db.flush()
    rows = ctx.db.execute(
        select(TicketViewer).where(
            TicketViewer.ticket_id == ticket.ticket_id,
            TicketViewer.user_id == officer,
        )
    ).scalars().all()
    assert len(rows) == 1
