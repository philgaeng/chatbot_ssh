"""
Celery: send one email per quarterly report assignment for the completed quarter.

Assignments are configured by local admins (max 3 per role per quarter).
"""
import logging
from datetime import date
from typing import Optional

from ticketing.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="ticketing.tasks.reports.dispatch_quarterly_report",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def dispatch_quarterly_report(
    self,
    organization_id: Optional[str] = None,
    quarter_key: Optional[str] = None,
) -> dict:
    from ticketing.models.base import SessionLocal
    from ticketing.services.quarterly_assignments import (
        list_assignments,
        quarter_date_range,
        quarter_key_from_date,
    )
    from ticketing.services.quarterly_report import (
        dispatch_assignment_email,
        generate_quarterly_xlsx,
        last_completed_quarter,
        resolve_recipient_emails,
    )

    if quarter_key:
        d_from, d_to = quarter_date_range(quarter_key)
        qk = quarter_key
    else:
        d_from, d_to = last_completed_quarter()
        qk = quarter_key_from_date(d_from)

    db = SessionLocal()
    sent = 0
    skipped = 0
    errors = 0
    try:
        assignments = list_assignments(db, quarter_key=qk, active_only=True)
        if not assignments:
            logger.warning("No quarterly assignments for %s", qk)
            return {"quarter_key": qk, "assignments": 0, "sent": 0, "skipped": 0}

        for assignment in assignments:
            role_key = assignment.get("role_key", "")
            template = assignment.get("template") or {}
            name = assignment.get("name") or "Quarterly report"
            aid = assignment.get("id", "")

            emails = resolve_recipient_emails(db, [role_key])
            if not emails:
                logger.warning("No emails for role %s — skip assignment %s", role_key, aid)
                skipped += 1
                continue

            try:
                xlsx_bytes, filename, ticket_count = generate_quarterly_xlsx(
                    db,
                    date_from=d_from,
                    date_to=d_to,
                    template=template,
                    organization_id=organization_id,
                )
            except Exception as exc:
                logger.exception("XLSX failed for assignment %s: %s", aid, exc)
                errors += 1
                continue

            ok = dispatch_assignment_email(
                db,
                assignment_id=aid,
                quarter_key=qk,
                role_key=role_key,
                emails=emails,
                date_from=d_from,
                date_to=d_to,
                ticket_count=ticket_count,
                template_name=name,
                xlsx_bytes=xlsx_bytes,
                filename=filename,
                actor_user_id="system",
            )
            if ok:
                sent += 1
            else:
                skipped += 1

        return {
            "quarter_key": qk,
            "date_from": str(d_from),
            "date_to": str(d_to),
            "assignments": len(assignments),
            "sent": sent,
            "skipped": skipped,
            "errors": errors,
        }
    except Exception as exc:
        logger.exception("dispatch_quarterly_report error: %s", exc)
        raise self.retry(exc=exc)
    finally:
        db.close()
