"""
SLA overdue episode lifecycle — docs/ticketing_system/09_reports_and_report_builder.md §14.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from ticketing.models.ticket import Ticket
from ticketing.models.ticket_overdue_episode import TicketOverdueEpisode
from ticketing.models.workflow import WorkflowStep

logger = logging.getLogger(__name__)
NEPAL_TZ = ZoneInfo("Asia/Kathmandu")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


def calendar_days_between(start: datetime, end: datetime) -> int:
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    d0 = start.astimezone(NEPAL_TZ).date()
    d1 = end.astimezone(NEPAL_TZ).date()
    return max(0, (d1 - d0).days)


def overdue_days_display(episode: TicketOverdueEpisode | None, *, at: datetime | None = None) -> int | None:
    if episode is None:
        return None
    end = episode.ended_at or (at or _now())
    return calendar_days_between(episode.started_at, end)


def sync_sla_breached_flag(ticket: Ticket) -> None:
    """Align legacy flag with open episode (§14)."""
    ticket.sla_breached = ticket.current_overdue_episode_id is not None


def get_open_episode(db: Session, ticket_id: str) -> TicketOverdueEpisode | None:
    return db.execute(
        select(TicketOverdueEpisode).where(
            TicketOverdueEpisode.ticket_id == ticket_id,
            TicketOverdueEpisode.ended_at.is_(None),
        )
    ).scalar_one_or_none()


def open_overdue_episode(
    db: Session,
    ticket: Ticket,
    step: WorkflowStep | None,
    *,
    triggered_by: str = "SLA_WATCHDOG",
    started_at: datetime | None = None,
) -> TicketOverdueEpisode:
    """Start an overdue stint; set tickets.current_overdue_episode_id."""
    existing = get_open_episode(db, ticket.ticket_id)
    if existing:
        ticket.current_overdue_episode_id = existing.episode_id
        sync_sla_breached_flag(ticket)
        return existing

    when = started_at or _now()
    episode = TicketOverdueEpisode(
        episode_id=_uuid(),
        ticket_id=ticket.ticket_id,
        workflow_step_id=step.step_id if step else ticket.current_step_id,
        step_order=int(step.step_order) if step else 1,
        assigned_to_user_id=ticket.assigned_to_user_id,
        assigned_role_id=ticket.assigned_role_id,
        started_at=when,
        triggered_by=triggered_by,
    )
    db.add(episode)
    ticket.current_overdue_episode_id = episode.episode_id
    sync_sla_breached_flag(ticket)
    logger.info(
        "Opened overdue episode ticket_id=%s episode_id=%s step_order=%s",
        ticket.ticket_id,
        episode.episode_id,
        episode.step_order,
    )
    return episode


def close_open_episode(
    db: Session,
    ticket: Ticket,
    end_reason: str,
    *,
    ended_at: datetime | None = None,
) -> TicketOverdueEpisode | None:
    """End the open episode (if any) and clear the ticket FK."""
    episode = None
    if ticket.current_overdue_episode_id:
        episode = db.get(TicketOverdueEpisode, ticket.current_overdue_episode_id)
    if episode is None:
        episode = get_open_episode(db, ticket.ticket_id)
    if episode is None or episode.ended_at is not None:
        ticket.current_overdue_episode_id = None
        sync_sla_breached_flag(ticket)
        return None

    when = ended_at or _now()
    episode.ended_at = when
    episode.end_reason = end_reason
    episode.days_overdue = calendar_days_between(episode.started_at, when)
    ticket.current_overdue_episode_id = None
    sync_sla_breached_flag(ticket)
    logger.info(
        "Closed overdue episode ticket_id=%s episode_id=%s reason=%s days=%s",
        ticket.ticket_id,
        episode.episode_id,
        end_reason,
        episode.days_overdue,
    )
    return episode


def ensure_breach_episode(
    db: Session,
    ticket: Ticket,
    step: WorkflowStep | None,
    *,
    triggered_by: str = "SLA_WATCHDOG",
) -> TicketOverdueEpisode | None:
    """Open episode when SLA is breached and none is open."""
    if ticket.current_overdue_episode_id:
        return db.get(TicketOverdueEpisode, ticket.current_overdue_episode_id)
    return open_overdue_episode(db, ticket, step, triggered_by=triggered_by)


def ticket_had_overdue_before(
    db: Session,
    ticket_id: str,
    before: datetime,
) -> bool:
    """Any completed or open episode that started before `before`."""
    if before.tzinfo is None:
        before = before.replace(tzinfo=timezone.utc)
    rows = db.execute(
        select(TicketOverdueEpisode.episode_id).where(
            TicketOverdueEpisode.ticket_id == ticket_id,
            TicketOverdueEpisode.started_at < before,
        )
    ).first()
    if rows:
        return True
    open_row = db.execute(
        select(TicketOverdueEpisode.episode_id).where(
            TicketOverdueEpisode.ticket_id == ticket_id,
            TicketOverdueEpisode.started_at <= before,
            TicketOverdueEpisode.ended_at.is_(None),
        )
    ).first()
    return open_row is not None


def episode_covers_instant(
    episode: TicketOverdueEpisode,
    instant: datetime,
) -> bool:
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    start = episode.started_at
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if start > instant:
        return False
    if episode.ended_at is None:
        return True
    end = episode.ended_at
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return end > instant


def load_episodes_for_tickets(
    db: Session,
    ticket_ids: list[str],
) -> dict[str, list[TicketOverdueEpisode]]:
    if not ticket_ids:
        return {}
    rows = db.execute(
        select(TicketOverdueEpisode)
        .where(TicketOverdueEpisode.ticket_id.in_(ticket_ids))
        .order_by(TicketOverdueEpisode.started_at)
    ).scalars().all()
    out: dict[str, list[TicketOverdueEpisode]] = {tid: [] for tid in ticket_ids}
    for ep in rows:
        out.setdefault(ep.ticket_id, []).append(ep)
    return out
