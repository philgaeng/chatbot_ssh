"""
Grievance sync task — keeps ticketing.tickets cache aligned with public.grievances.

Runs every 2 minutes via Celery Beat (see celery_app.py beat_schedule).

Design (Option A — primary routing via chatbot webhook):
  - **UPDATE** existing tickets when summary/categories/location change on the grievance row.
  - **CREATE** only as backfill when no ticket exists AND the grievance is older than a grace
    period (webhook had time to run). Backfill uses the same intake path as POST /api/v1/tickets
    (workflow resolution + auto-assign; best-effort location from complainant join).
  - Does NOT race the chatbot dispatch_ticket path for fresh grievances.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from celery import shared_task
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ticketing.models.base import SessionLocal
from ticketing.models.ticket import Ticket
from ticketing.services.grievance_content import _coerce_categories
from ticketing.services.grievance_sync_policy import should_attempt_backfill
from ticketing.services.ticket_intake import (
    DuplicateTicketError,
    TicketIntakeError,
    build_backfill_payload_from_grievance_row,
    create_ticket_from_intake,
)

logger = logging.getLogger(__name__)

# Seconds to wait after grievance creation before sync may backfill a missing ticket.
_DEFAULT_BACKFILL_GRACE_SECONDS = 180


def _backfill_grace_seconds() -> int:
    try:
        from ticketing.config.settings import get_settings

        configured = get_settings().ticketing_sync_backfill_grace_seconds
    except Exception:
        configured = _DEFAULT_BACKFILL_GRACE_SECONDS
    raw = os.getenv("TICKETING_SYNC_BACKFILL_GRACE_SECONDS", str(configured))
    try:
        return max(60, int(raw))
    except ValueError:
        return max(60, int(configured))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fetch_all_grievance_rows(db: Session) -> list[dict]:
    result = db.execute(text("""
        SELECT
            g.grievance_id,
            g.complainant_id,
            g.grievance_summary,
            g.grievance_categories,
            g.grievance_location,
            g.grievance_high_priority,
            g.grievance_sensitive_issue,
            g.grievance_creation_date,
            g.source,
            c.location_code AS location_code
        FROM public.grievances g
        LEFT JOIN public.grievance_parties gp
            ON g.grievance_id = gp.grievance_id AND gp.is_primary_reporter IS TRUE
        LEFT JOIN public.complainants c ON gp.complainant_id = c.complainant_id
        ORDER BY g.grievance_creation_date ASC
    """))
    return [dict(r) for r in result.mappings().all()]


def _cache_needs_update(ticket: Ticket, g: dict) -> bool:
    cats = _coerce_categories(g.get("grievance_categories"))
    if g.get("grievance_summary") and ticket.grievance_summary != g.get("grievance_summary"):
        return True
    if cats and ticket.grievance_categories != cats:
        return True
    if g.get("grievance_location") and ticket.grievance_location != g.get("grievance_location"):
        return True
    return False


def _apply_cache(ticket: Ticket, g: dict) -> None:
    ticket.grievance_summary = g.get("grievance_summary") or ticket.grievance_summary
    cats = _coerce_categories(g.get("grievance_categories"))
    if cats:
        ticket.grievance_categories = cats
    if g.get("grievance_location"):
        ticket.grievance_location = g.get("grievance_location")
    ticket.updated_at = _now()


def _backfill_ticket_from_grievance(db: Session, g: dict) -> Optional[Ticket]:
    """Create ticket via shared intake service (auto-assign, workflow). Returns None on skip/error."""
    try:
        payload = build_backfill_payload_from_grievance_row(g)
        return create_ticket_from_intake(
            db,
            payload,
            source="sync_backfill",
            created_by_user_id="system",
        )
    except DuplicateTicketError:
        return None
    except TicketIntakeError as exc:
        logger.warning(
            "grievance_sync: backfill skipped for %s: %s",
            g.get("grievance_id"),
            exc.detail,
        )
        return None


@shared_task(
    bind=True,
    name="ticketing.tasks.grievance_sync.sync_grievances",
    max_retries=3,
    default_retry_delay=60,
)
def sync_grievances(self) -> dict:
    db: Session = SessionLocal()
    created = updated = skipped = pending_webhook = errors = 0
    created_ticket_ids: list[str] = []
    grace = _backfill_grace_seconds()
    sync_now = _now()

    try:
        grievances = _fetch_all_grievance_rows(db)
        if not grievances:
            return {
                "created": 0,
                "updated": 0,
                "skipped": 0,
                "pending_webhook": 0,
                "errors": 0,
            }

        tickets_by_gid = {
            t.grievance_id: t
            for t in db.execute(select(Ticket).where(Ticket.is_deleted.is_(False))).scalars().all()
        }

        for g in grievances:
            gid = g["grievance_id"]
            try:
                existing = tickets_by_gid.get(gid)
                if existing:
                    if _cache_needs_update(existing, g):
                        _apply_cache(existing, g)
                        updated += 1
                        logger.info("grievance_sync: updated cache for ticket %s", existing.ticket_id)
                    else:
                        skipped += 1
                    continue

                if not should_attempt_backfill(g, now=sync_now, grace_seconds=grace):
                    pending_webhook += 1
                    logger.debug(
                        "grievance_sync: awaiting webhook for %s (age < %ss)",
                        gid,
                        grace,
                    )
                    continue

                ticket = _backfill_ticket_from_grievance(db, g)
                if ticket:
                    tickets_by_gid[gid] = ticket
                    created += 1
                    created_ticket_ids.append(ticket.ticket_id)
                    logger.info(
                        "grievance_sync: backfill ticket %s for %s",
                        ticket.ticket_id,
                        gid,
                    )
                else:
                    skipped += 1
            except Exception as exc:
                errors += 1
                logger.error("grievance_sync: %s: %s", gid, exc, exc_info=True)

        if created > 0 or updated > 0:
            db.commit()
            logger.info(
                "grievance_sync: committed created=%d updated=%d pending_webhook=%d",
                created,
                updated,
                pending_webhook,
            )
            if created_ticket_ids:
                from ticketing.tasks.llm import generate_findings

                for tid in created_ticket_ids:
                    try:
                        generate_findings.delay(tid)
                    except Exception as exc:
                        logger.warning(
                            "grievance_sync: could not queue findings for %s: %s",
                            tid,
                            exc,
                        )

    except Exception as exc:
        db.rollback()
        logger.exception("grievance_sync: fatal error")
        raise self.retry(exc=exc)
    finally:
        db.close()

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "pending_webhook": pending_webhook,
        "errors": errors,
    }
