"""
Grievance sync task — keeps ticketing.tickets cache aligned with public.grievances.

Runs every 2 minutes via Celery Beat (see celery_app.py beat_schedule).

Design (Option A — primary routing via chatbot webhook):
  - **UPDATE** existing tickets when summary/categories/location change on the grievance row.
  - **CREATE** only as backfill when no ticket exists AND the grievance is older than a grace
    period (webhook had time to run). Backfill uses the same intake path as POST /api/v1/tickets
    (workflow resolution + auto-assign; best-effort location from complainant join).
  - Does NOT race the chatbot dispatch_ticket path for fresh grievances.

Watermark-incremental scan (H2-04):
  - A high-water mark (max ``grievance_modification_date`` processed) is persisted in
    ``ticketing.settings`` under ``grievance_sync_watermark``. Each run only fetches rows
    modified since the watermark, keyset-paged by ``(grievance_modification_date, grievance_id)``
    in batches of ``ticketing_sync_batch_size`` (default 500) until exhausted. This replaces the
    old O(all-time) full scan of every ``public.grievances`` row on every 2-min tick.
  - The watermark advances **after** each page commits (crash-safe: re-processing a page is
    idempotent — existing-ticket refresh no-ops on unchanged data, and backfill dedups on the
    HR-03 unique index, so a crash before the watermark commit converges on re-run with no
    duplicate tickets).
  - The watermark never advances **past a still-pending backfill** (a fresh grievance seen while
    inside the grace window, deferred as ``pending_webhook``). Otherwise a later webhook failure
    would leave that grievance un-backfilled until the daily full sweep. Pending rows stay in the
    window until they age out of grace and get backfilled.

  Known watermark gap (hybrid fallback): ``location_code`` comes from the complainant join, and
  complainant edits run ``UPDATE complainants`` without bumping ``grievance_modification_date`` —
  so a location-only change is invisible to the incremental scan. A daily ``full=True`` sweep
  (celery beat ``grm-grievance-sync-full``) backstops this; ops can also trigger it on demand.

Full sweep (ops escape hatch):
  ``sync_grievances.delay(full=True)`` (or ``.apply(kwargs={"full": True})``) ignores the
  watermark and scans every non-temporary grievance, then re-stamps the watermark. Wired daily
  in celery beat as the hybrid backstop for join-sourced changes above.
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
from ticketing.models.settings import Settings
from ticketing.models.ticket import Ticket
from ticketing.services.grievance_content import _coerce_categories
from ticketing.services.grievance_sync_policy import should_attempt_backfill
from ticketing.services.ticket_intake import (
    DuplicateTicketError,
    TicketIntakeError,
    build_backfill_payload_from_grievance_row,
    create_ticket_from_intake,
    refresh_ticket_routing_from_intake,
)

logger = logging.getLogger(__name__)

# Seconds to wait after grievance creation before sync may backfill a missing ticket.
_DEFAULT_BACKFILL_GRACE_SECONDS = 180

# ticketing.settings key holding the max grievance_modification_date processed (ISO string).
_WATERMARK_KEY = "grievance_sync_watermark"

# Watermark floor for a full sweep / first run — before any grievance could exist.
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

_DEFAULT_BATCH_SIZE = 500


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


def _batch_size() -> int:
    try:
        from ticketing.config.settings import get_settings

        configured = get_settings().ticketing_sync_batch_size
    except Exception:
        configured = _DEFAULT_BATCH_SIZE
    raw = os.getenv("TICKETING_SYNC_BATCH_SIZE", str(configured))
    try:
        return max(1, int(raw))
    except ValueError:
        return max(1, int(configured))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _load_watermark(db: Session) -> tuple[datetime, str]:
    """Persisted keyset position (max grievance_modification_date, grievance_id) processed.

    Returns (_EPOCH, "") when unset/unparsable. The grievance_id half makes the cross-run
    boundary a strict keyset resume: a no-change run re-fetches nothing (satisfies the
    "run 2 = zero rows" DoD) while ties at the same modification timestamp are never skipped.
    """
    row = db.get(Settings, _WATERMARK_KEY)
    if not row or not isinstance(row.value, dict):
        return _EPOCH, ""
    raw = row.value.get("watermark")
    gid = row.value.get("watermark_gid") or ""
    if not raw:
        return _EPOCH, ""
    try:
        return (_as_utc(datetime.fromisoformat(raw)) or _EPOCH, gid)
    except (TypeError, ValueError):
        return _EPOCH, ""


def _save_watermark(db: Session, watermark: datetime, watermark_gid: str) -> None:
    """Upsert the keyset watermark and commit (its own txn, after the page data commit)."""
    value = {
        "watermark": _as_utc(watermark).isoformat(),
        "watermark_gid": watermark_gid,
        "updated_at": _now().isoformat(),
    }
    row = db.get(Settings, _WATERMARK_KEY)
    if row:
        row.value = value
        row.updated_by_user_id = "system"
    else:
        db.add(Settings(key=_WATERMARK_KEY, value=value, updated_by_user_id="system"))
    db.commit()


def _fetch_grievance_page(
    db: Session, *, after_date: datetime, after_gid: str, limit: int
) -> list[dict]:
    """One keyset page of grievances modified after (after_date, after_gid), ascending.

    Keyset on (grievance_modification_date, grievance_id) makes paging deterministic and
    tie-safe: rows sharing a modification timestamp are ordered by grievance_id, so the page
    boundary never drops or repeats a row within a run.
    """
    result = db.execute(
        text("""
        SELECT
            g.grievance_id,
            g.complainant_id,
            g.grievance_summary,
            g.grievance_categories,
            g.grievance_location,
            g.grievance_high_priority,
            g.grievance_sensitive_issue,
            g.grievance_creation_date,
            g.grievance_modification_date,
            g.source,
            c.location_code AS location_code
        FROM public.grievances g
        LEFT JOIN public.grievance_parties gp
            ON g.grievance_id = gp.grievance_id AND gp.is_primary_reporter IS TRUE
        LEFT JOIN public.complainants c ON gp.complainant_id = c.complainant_id
        WHERE g.grievance_modification_date > :after_date
           OR (g.grievance_modification_date = :after_date AND g.grievance_id > :after_gid)
        ORDER BY g.grievance_modification_date ASC, g.grievance_id ASC
        LIMIT :limit
        """),
        {"after_date": after_date, "after_gid": after_gid, "limit": limit},
    )
    return [dict(r) for r in result.mappings().all()]


def _cache_needs_update(ticket: Ticket, g: dict) -> bool:
    cats = _coerce_categories(g.get("grievance_categories"))
    if g.get("grievance_summary") and ticket.grievance_summary != g.get("grievance_summary"):
        return True
    if cats and ticket.grievance_categories != cats:
        return True
    if g.get("grievance_location") and ticket.grievance_location != g.get("grievance_location"):
        return True
    loc = g.get("location_code")
    if loc and ticket.location_code != loc:
        return True
    return False


def _apply_cache(ticket: Ticket, g: dict) -> None:
    ticket.grievance_summary = g.get("grievance_summary") or ticket.grievance_summary
    cats = _coerce_categories(g.get("grievance_categories"))
    if cats:
        ticket.grievance_categories = cats
    if g.get("grievance_location"):
        ticket.grievance_location = g.get("grievance_location")
    loc = g.get("location_code")
    if loc:
        ticket.location_code = loc
    ticket.updated_at = _now()


def _refresh_existing_ticket(db: Session, ticket: Ticket, g: dict) -> bool:
    """Sync grievance text/location onto ticket and retry auto-assign when still unassigned."""
    had_cache = _cache_needs_update(ticket, g)
    if had_cache:
        _apply_cache(ticket, g)
    try:
        payload = build_backfill_payload_from_grievance_row(g)
        refresh_ticket_routing_from_intake(db, payload, source="sync_refresh")
        return True
    except TicketIntakeError as exc:
        logger.warning(
            "grievance_sync: refresh skipped for %s: %s",
            g.get("grievance_id"),
            exc.detail,
        )
        return had_cache


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
    except DuplicateTicketError as exc:
        # HR-03: a ticket already exists for this grievance (webhook won the race, or a
        # concurrent sync). Skip-and-continue — this is expected, not an error.
        logger.info(
            "grievance_sync: backfill skipped for %s — ticket %s already exists",
            g.get("grievance_id"),
            exc.ticket_id,
        )
        return None
    except TicketIntakeError as exc:
        logger.warning(
            "grievance_sync: backfill skipped for %s: %s",
            g.get("grievance_id"),
            exc.detail,
        )
        return None


def run_grievance_sync(
    db: Session, *, full: bool = False, now: Optional[datetime] = None
) -> dict:
    """Core incremental grievance→ticket cache sync (no Celery / session lifecycle).

    Mirrors the ``run_sla_check(db)`` core+task split so tests can drive it on a caller-owned
    session. The bound task ``sync_grievances`` wraps this with SessionLocal, findings enqueue,
    and retry-on-fatal.

    Args:
        full: ignore the watermark and scan every grievance (ops full sweep / daily join-gap
            backstop). Re-stamps the watermark on completion.
        now: reference time for grace evaluation (tests inject; defaults to utcnow).

    Returns the run summary plus ``created_ticket_ids`` (the task wrapper enqueues findings).
    """
    created = updated = skipped = pending_webhook = errors = 0
    fetched = pages = 0
    created_ticket_ids: list[str] = []
    grace = _backfill_grace_seconds()
    batch = _batch_size()
    sync_now = now or _now()

    start_date, start_gid = (_EPOCH, "") if full else _load_watermark(db)
    cursor_date, cursor_gid = start_date, start_gid
    # Smallest modification time of a row deferred as pending_webhook this run: the watermark
    # must never advance past it, so the deferred backfill is retried next run.
    run_min_pending: Optional[datetime] = None
    final_date, final_gid = start_date, start_gid

    while True:
        page = _fetch_grievance_page(
            db, after_date=cursor_date, after_gid=cursor_gid, limit=batch
        )
        if not page:
            break
        pages += 1
        fetched += len(page)

        page_gids = [g["grievance_id"] for g in page]
        tickets_by_gid = {
            t.grievance_id: t
            for t in db.execute(
                select(Ticket).where(
                    Ticket.grievance_id.in_(page_gids),
                    Ticket.is_deleted.is_(False),
                )
            ).scalars().all()
        }

        for g in page:
            gid = g["grievance_id"]
            try:
                existing = tickets_by_gid.get(gid)
                if existing:
                    if _refresh_existing_ticket(db, existing, g):
                        updated += 1
                        logger.info("grievance_sync: refreshed ticket %s", existing.ticket_id)
                    else:
                        skipped += 1
                    continue

                if not should_attempt_backfill(g, now=sync_now, grace_seconds=grace):
                    pending_webhook += 1
                    mod = _as_utc(g.get("grievance_modification_date"))
                    if mod is not None and (run_min_pending is None or mod < run_min_pending):
                        run_min_pending = mod
                    logger.debug(
                        "grievance_sync: awaiting webhook for %s (age < %ss)", gid, grace
                    )
                    continue

                ticket = _backfill_ticket_from_grievance(db, g)
                if ticket:
                    tickets_by_gid[gid] = ticket
                    created += 1
                    created_ticket_ids.append(ticket.ticket_id)
                    logger.info(
                        "grievance_sync: backfill ticket %s for %s", ticket.ticket_id, gid
                    )
                else:
                    skipped += 1
            except Exception as exc:
                errors += 1
                logger.error("grievance_sync: %s: %s", gid, exc, exc_info=True)

        # Advance the in-run keyset cursor to the last row of the page (always moves forward →
        # paging terminates even with many identical timestamps).
        last = page[-1]
        cursor_date = _as_utc(last.get("grievance_modification_date")) or cursor_date
        cursor_gid = last["grievance_id"]

        # Persisted keyset watermark = page frontier, unless a backfill is still pending: then
        # park at (oldest-pending mod time, "") so the strict keyset resume re-includes that row
        # (and everything after it) next run without re-scanning settled rows before it.
        if run_min_pending is not None:
            save_date, save_gid = run_min_pending, ""
        else:
            save_date, save_gid = cursor_date, cursor_gid
        # Monotonic: never move the watermark backwards relative to where this run started.
        if (save_date, save_gid) < (start_date, start_gid):
            save_date, save_gid = start_date, start_gid

        # Crash-safe ordering: commit the page's ticket changes first, then advance the watermark
        # in a separate commit. A crash in between leaves the watermark stale and the next run
        # reprocesses this page idempotently (HR-03 dedup + no-op refresh).
        db.commit()
        _save_watermark(db, save_date, save_gid)
        final_date, final_gid = save_date, save_gid

        if len(page) < batch:
            break

    if created or updated or pending_webhook:
        logger.info(
            "grievance_sync: fetched=%d pages=%d created=%d updated=%d "
            "skipped=%d pending_webhook=%d errors=%d",
            fetched, pages, created, updated, skipped, pending_webhook, errors,
        )

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "pending_webhook": pending_webhook,
        "errors": errors,
        "fetched": fetched,
        "pages": pages,
        "full": full,
        "watermark": _as_utc(final_date).isoformat(),
        "watermark_gid": final_gid,
        "created_ticket_ids": created_ticket_ids,
    }


@shared_task(
    bind=True,
    name="ticketing.tasks.grievance_sync.sync_grievances",
    max_retries=3,
    default_retry_delay=60,
)
def sync_grievances(self, full: bool = False) -> dict:
    """Incremental grievance→ticket cache sync (Celery beat every 2 min; daily full sweep).

    Args:
        full: when True, ignore the watermark and scan every grievance (ops full sweep /
            daily join-gap backstop). Re-stamps the watermark on completion.
    """
    db: Session = SessionLocal()
    try:
        result = run_grievance_sync(db, full=full)
        created_ticket_ids = result.pop("created_ticket_ids", [])
        if created_ticket_ids:
            from ticketing.tasks.llm import generate_findings

            for tid in created_ticket_ids:
                try:
                    generate_findings.delay(tid)
                except Exception as exc:
                    logger.warning(
                        "grievance_sync: could not queue findings for %s: %s", tid, exc
                    )
        return result
    except Exception as exc:
        db.rollback()
        logger.exception("grievance_sync: fatal error")
        raise self.retry(exc=exc)
    finally:
        db.close()
