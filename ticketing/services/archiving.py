"""
Resolved-case archiving — eligibility, selection, and archive execution.

Policy: docs/ARCHIVING_AND_RETENTION.md §2–§7.
"""
from __future__ import annotations

import logging
import os
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ticketing.clients import grievance_api
from ticketing.models.admin_audit_log import AdminAuditLog
from ticketing.models.ticket import Ticket, TicketEvent
from ticketing.models.ticket_resolved_summary import TicketResolvedSummary
from ticketing.services.archiving_policy import load_archiving_policy

logger = logging.getLogger(__name__)

RESOLVED_STATUSES = frozenset({"RESOLVED", "CLOSED"})


@dataclass
class ArchiveResult:
    ticket_id: str
    grievance_id: str
    archived: bool
    skipped_reason: str | None = None
    attachments_tiered: int = 0
    dry_run: bool = False


@dataclass
class ArchiveJobSummary:
    as_of: date
    candidates: int = 0
    archived: int = 0
    skipped: int = 0
    errors: int = 0
    dry_run: bool = False
    details: list[ArchiveResult] = field(default_factory=list)


def archive_eligible_date(
    resolved_at: datetime,
    years_before_archiving: int,
    tz_name: str,
    *,
    archive_run_month: int = 1,
    archive_run_day: int = 2,
) -> date:
    """
    N = calendar year of resolution in tz_name.
    Eligible from archive_run_month/archive_run_day, year N + 1 + years_before_archiving.
    """
    if resolved_at.tzinfo is None:
        resolved_at = resolved_at.replace(tzinfo=timezone.utc)
    local = resolved_at.astimezone(ZoneInfo(tz_name))
    n = local.year
    return date(n + 1 + years_before_archiving, archive_run_month, archive_run_day)


def _years_for_ticket(ticket: Ticket, policy: dict[str, Any]) -> int:
    if ticket.is_seah and policy.get("seah_years_before_archiving") is not None:
        return int(policy["seah_years_before_archiving"])
    return int(policy["years_before_archiving"])


def get_resolution_timestamp(db: Session, ticket: Ticket) -> datetime | None:
    """L1: latest RESOLVED event; fallback ticket_resolved_summaries.resolved_at."""
    row = db.execute(
        select(TicketEvent.created_at)
        .where(
            TicketEvent.ticket_id == ticket.ticket_id,
            TicketEvent.event_type == "RESOLVED",
        )
        .order_by(TicketEvent.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if row is not None:
        return row

    summary = db.get(TicketResolvedSummary, ticket.ticket_id)
    if summary is not None:
        return summary.resolved_at
    return None


def is_ticket_eligible(
    db: Session,
    ticket: Ticket,
    policy: dict[str, Any],
    as_of: date,
) -> tuple[bool, str | None]:
    if ticket.is_archived or ticket.archived_at is not None:
        return False, "already_archived"
    if ticket.status_code not in RESOLVED_STATUSES:
        return False, "not_resolved"
    if ticket.is_deleted:
        return False, "deleted"

    resolved_at = get_resolution_timestamp(db, ticket)
    if resolved_at is None:
        return False, "no_resolution_timestamp"

    years = _years_for_ticket(ticket, policy)
    eligible_from = archive_eligible_date(
        resolved_at,
        years,
        policy.get("timezone", "Asia/Kathmandu"),
        archive_run_month=int(policy.get("archive_run_month", 1)),
        archive_run_day=int(policy.get("archive_run_day", 2)),
    )
    if as_of < eligible_from:
        return False, f"not_yet_eligible:{eligible_from.isoformat()}"
    return True, None


def select_eligible_tickets(
    db: Session,
    policy: dict[str, Any],
    as_of: date | None = None,
) -> list[Ticket]:
    as_of = as_of or date.today()
    q = select(Ticket).where(
        Ticket.is_deleted.is_(False),
        Ticket.is_archived.is_(False),
        Ticket.archived_at.is_(None),
        Ticket.status_code.in_(tuple(RESOLVED_STATUSES)),
    )
    tickets = db.execute(q).scalars().all()
    eligible: list[Ticket] = []
    for ticket in tickets:
        ok, reason = is_ticket_eligible(db, ticket, policy, as_of)
        if ok:
            eligible.append(ticket)
        elif reason == "no_resolution_timestamp":
            logger.warning(
                "archive skip: ticket=%s grievance=%s — no RESOLVED event or resolved summary",
                ticket.ticket_id,
                ticket.grievance_id,
            )
    return eligible


def _tier_attachments(
    db: Session,
    grievance_id: str,
    policy: dict[str, Any],
) -> int:
    tier_mode = policy.get("attachment_tier_on_archive", "none")
    if tier_mode == "none":
        return 0

    upload_root = os.getenv("UPLOAD_FOLDER", "uploads")
    now = datetime.now(timezone.utc)

    try:
        rows = db.execute(
            text(
                """
                SELECT file_id, file_path, file_name
                FROM public.file_attachments
                WHERE grievance_id = :gid
                """
            ),
            {"gid": grievance_id},
        ).mappings().all()
    except Exception as exc:
        logger.warning("tier_attachments: file_attachments unavailable — %s", exc)
        db.rollback()
        return 0

    count = 0
    for row in rows:
        file_id = row["file_id"]
        src_path = row["file_path"]
        ext = os.path.splitext(row["file_name"] or src_path)[1] or ""
        storage_key = f"archive/{grievance_id}/{file_id}{ext}"

        if tier_mode == "cold" and os.path.isfile(src_path):
            dest_path = os.path.join(upload_root, storage_key)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            if not os.path.isfile(dest_path):
                shutil.copy2(src_path, dest_path)

        db.execute(
            text(
                """
                UPDATE public.file_attachments
                SET storage_tier = :tier,
                    storage_key = :key,
                    archived_at = :archived_at
                WHERE file_id = :fid
                """
            ),
            {
                "tier": "archive" if tier_mode in ("cold", "glacier") else "active",
                "key": storage_key if tier_mode == "cold" else None,
                "archived_at": now,
                "fid": file_id,
            },
        )
        count += 1
    return count


def archive_ticket(
    db: Session,
    ticket: Ticket,
    policy: dict[str, Any],
    *,
    dry_run: bool = False,
    actor_user_id: str = "system:archive_job",
) -> ArchiveResult:
    if ticket.is_archived or ticket.archived_at is not None:
        return ArchiveResult(
            ticket_id=ticket.ticket_id,
            grievance_id=ticket.grievance_id,
            archived=False,
            skipped_reason="already_archived",
            dry_run=dry_run,
        )

    if dry_run:
        return ArchiveResult(
            ticket_id=ticket.ticket_id,
            grievance_id=ticket.grievance_id,
            archived=True,
            dry_run=True,
        )

    now = datetime.now(timezone.utc)
    ticket.is_archived = True
    ticket.archived_at = now
    ticket.updated_at = now

    try:
        grievance_api.update_grievance_status(
            ticket.grievance_id,
            "archived",
            note="Case archived by GRM retention policy",
        )
    except Exception as exc:
        logger.error(
            "archive_ticket: grievance API failed ticket=%s grievance=%s — %s",
            ticket.ticket_id,
            ticket.grievance_id,
            exc,
        )
        db.rollback()
        raise

    attachments_tiered = _tier_attachments(db, ticket.grievance_id, policy)

    event = TicketEvent(
        event_id=str(uuid.uuid4()),
        ticket_id=ticket.ticket_id,
        event_type="CASE_ARCHIVED",
        note="Case archived per retention policy",
        payload={
            "event_type": "CASE_ARCHIVED",
            "grievance_id": ticket.grievance_id,
            "archived_at": now.isoformat(),
            "attachment_tier": policy.get("attachment_tier_on_archive"),
        },
        seen=True,
        created_by_user_id=actor_user_id,
        case_sensitivity="seah" if ticket.is_seah else "standard",
    )
    db.add(event)

    db.add(
        AdminAuditLog(
            actor_user_id=actor_user_id,
            action="case_archived",
            payload={
                "ticket_id": ticket.ticket_id,
                "grievance_id": ticket.grievance_id,
                "attachments_tiered": attachments_tiered,
            },
        )
    )
    db.flush()

    return ArchiveResult(
        ticket_id=ticket.ticket_id,
        grievance_id=ticket.grievance_id,
        archived=True,
        attachments_tiered=attachments_tiered,
    )


def clear_archive_on_reopen(db: Session, ticket: Ticket) -> None:
    """L2: clear archive flags when ticket leaves RESOLVED/CLOSED."""
    if not ticket.is_archived and ticket.archived_at is None:
        return

    ticket.is_archived = False
    ticket.archived_at = None
    ticket.updated_at = datetime.now(timezone.utc)

    try:
        grievance_api.update_grievance_status(
            ticket.grievance_id,
            "in_progress",
            note="Case reopened — archive flags cleared",
        )
    except Exception as exc:
        logger.warning(
            "clear_archive_on_reopen: grievance API failed grievance=%s — %s",
            ticket.grievance_id,
            exc,
        )


def run_archive_job(
    db: Session,
    *,
    as_of: date | None = None,
    dry_run: bool | None = None,
) -> ArchiveJobSummary:
    from ticketing.config.settings import get_settings

    settings = get_settings()
    if dry_run is None:
        dry_run = settings.archiving_dry_run

    policy = load_archiving_policy(db)
    as_of = as_of or date.today()
    summary = ArchiveJobSummary(as_of=as_of, dry_run=dry_run)

    if not policy.get("enabled", True):
        logger.info("archive job: disabled in archiving_policy — no-op")
        return summary

    candidates = select_eligible_tickets(db, policy, as_of)
    summary.candidates = len(candidates)

    for ticket in candidates:
        try:
            result = archive_ticket(db, ticket, policy, dry_run=dry_run)
            summary.details.append(result)
            if result.archived and not result.skipped_reason:
                summary.archived += 1
            elif result.skipped_reason:
                summary.skipped += 1
        except Exception:
            summary.errors += 1
            logger.exception("archive job failed for ticket=%s", ticket.ticket_id)

    if not dry_run:
        db.commit()
    else:
        db.rollback()

    logger.info(
        "archive job complete: as_of=%s candidates=%s archived=%s skipped=%s errors=%s dry_run=%s",
        as_of,
        summary.candidates,
        summary.archived,
        summary.skipped,
        summary.errors,
        dry_run,
    )
    return summary
