"""
Backfill ticket_overdue_episodes from SLA-related ticket_events (demo / legacy rows).

Usage:
  python -m ticketing.seed.backfill_overdue_episodes
"""
from __future__ import annotations

import logging

from sqlalchemy import select

from ticketing.models.base import SessionLocal
from ticketing.engine.workflow_engine import get_current_step, is_sla_breached
from ticketing.models.ticket import Ticket, TicketEvent
from ticketing.models.workflow import WorkflowStep
from ticketing.services.overdue_episodes import (
    close_open_episode,
    get_open_episode,
    open_overdue_episode,
)

logger = logging.getLogger(__name__)


def backfill(*, dry_run: bool = False) -> int:
    created = 0
    with SessionLocal() as db:
        tickets = db.execute(
            select(Ticket).where(Ticket.is_deleted.is_(False))
        ).scalars().all()
        for ticket in tickets:
            if get_open_episode(db, ticket.ticket_id):
                continue
            events = db.execute(
                select(TicketEvent)
                .where(TicketEvent.ticket_id == ticket.ticket_id)
                .order_by(TicketEvent.created_at)
            ).scalars().all()
            for ev in events:
                payload = ev.payload or {}
                trig = payload.get("triggered_by", "")
                if ev.event_type in ("SLA_BREACH_FINAL_STEP",) or (
                    ev.event_type == "ESCALATED" and trig == "SLA_AUTO"
                ):
                    step = (
                        db.get(WorkflowStep, ev.workflow_step_id)
                        if ev.workflow_step_id
                        else get_current_step(ticket, db)
                    )
                    if dry_run:
                        created += 1
                        break
                    open_overdue_episode(
                        db,
                        ticket,
                        step,
                        triggered_by="SLA_AUTO_ESCALATE",
                        started_at=ev.created_at,
                    )
                    if ev.event_type == "ESCALATED":
                        close_open_episode(db, ticket, "ESCALATED", ended_at=ev.created_at)
                    created += 1
                    break
            else:
                if ticket.status_code not in ("RESOLVED", "CLOSED"):
                    step = get_current_step(ticket, db)
                    if step and is_sla_breached(ticket, step):
                        if dry_run:
                            created += 1
                        else:
                            open_overdue_episode(
                                db, ticket, step, triggered_by="SLA_WATCHDOG"
                            )
                            created += 1
        if not dry_run:
            db.commit()
    logger.info("Backfill complete: %s episodes touched", created)
    return created


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    n = backfill()
    print(f"Backfill created/updated {n} episode records")
