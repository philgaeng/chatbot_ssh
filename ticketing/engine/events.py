# SPDX-License-Identifier: Apache-2.0

"""Canonical ticket-event writer (H2-02).

Single definition of `_add_event`, shared by the router action path
(`api/routers/tickets/…`) and the escalation engine (`engine/escalation.py`).
Previously duplicated in both with near-identical 15-parameter signatures.

Imports **models only** — must never import routers or `engine.escalation`, so it
stays a leaf with no import cycle.
"""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from ticketing.models.ticket import Ticket, TicketEvent


def _case_sensitivity(ticket: Ticket) -> str:
    return "seah" if ticket.is_seah else "standard"


def _add_event(
    db: Session,
    ticket: Ticket,
    event_type: str,
    *,
    old_status: Optional[str] = None,
    new_status: Optional[str] = None,
    old_assigned: Optional[str] = None,
    new_assigned: Optional[str] = None,
    step_id: Optional[str] = None,
    note: Optional[str] = None,
    payload: Optional[dict] = None,
    created_by: Optional[str] = None,
    seen: bool = False,
    notify_user_id: Optional[str] = None,
    # ── SEAH audit fields (seah-privacy-worktree-handoff.md) ──
    actor_role: Optional[str] = None,
    case_sensitivity: Optional[str] = None,   # derived from ticket when None
    summary_regen_required: bool = False,
) -> TicketEvent:
    event = TicketEvent(
        event_id=str(uuid.uuid4()),
        ticket_id=ticket.ticket_id,
        event_type=event_type,
        old_status_code=old_status,
        new_status_code=new_status,
        old_assigned_to=old_assigned,
        new_assigned_to=new_assigned,
        workflow_step_id=step_id,
        note=note,
        payload=payload,
        seen=seen,
        assigned_to_user_id=notify_user_id,
        created_by_user_id=created_by,
        actor_role=actor_role,
        case_sensitivity=case_sensitivity if case_sensitivity is not None else _case_sensitivity(ticket),
        summary_regen_required=summary_regen_required,
    )
    db.add(event)
    return event
