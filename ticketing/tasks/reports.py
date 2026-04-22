"""
Celery tasks: quarterly GRM report generation and email dispatch.

Schedule: 5th of January, April, July, October at 06:00 UTC
         (configured in celery_app.py beat_schedule)

Recipients: roles adb_national_project_director, adb_hq_safeguards, adb_hq_project
            → user_ids from ticketing.user_roles → email lookup from Cognito
            INTEGRATION POINT: Cognito ListUsers to get officer emails

On-demand export is also available via the /api/v1/reports/export HTTP endpoint
(reports.py router).
"""
import io
import logging
from datetime import date, timedelta
from typing import Optional

from ticketing.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# Roles that receive quarterly reports (CLAUDE.md REPORTS section)
REPORT_RECIPIENT_ROLES = {
    "adb_national_project_director",
    "adb_hq_safeguards",
    "adb_hq_project",
}


@celery_app.task(
    name="ticketing.tasks.reports.dispatch_quarterly_report",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def dispatch_quarterly_report(
    self,
    organization_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> dict:
    """
    Generate XLSX quarterly report and email to report recipient roles.

    date_from / date_to: ISO date strings (default: last quarter).
    """
    from sqlalchemy import func, select
    from ticketing.models.base import SessionLocal
    from ticketing.models.ticket import Ticket
    from ticketing.models.user import Role, UserRole
    from ticketing.api.routers.reports import _build_xlsx
    from ticketing.clients.messaging_api import send_email

    # Resolve date range
    if date_from and date_to:
        d_from = date.fromisoformat(date_from)
        d_to = date.fromisoformat(date_to)
    else:
        today = date.today()
        d_to = today
        d_from = today - timedelta(days=91)  # ~quarter

    db = SessionLocal()
    try:
        # Query tickets for the period
        q = (
            select(Ticket)
            .where(
                Ticket.is_deleted.is_(False),
                Ticket.is_seah.is_(False),  # exclude SEAH from standard report
                func.date(Ticket.created_at) >= d_from,
                func.date(Ticket.created_at) <= d_to,
            )
            .order_by(Ticket.created_at)
        )
        if organization_id:
            q = q.where(Ticket.organization_id == organization_id)

        tickets = db.execute(q).scalars().all()
        xlsx_bytes = _build_xlsx(tickets)

        # Find recipient user_ids by role
        recipient_roles = db.execute(
            select(Role).where(Role.role_key.in_(REPORT_RECIPIENT_ROLES))
        ).scalars().all()
        role_ids = [r.role_id for r in recipient_roles]

        recipient_user_ids = db.execute(
            select(UserRole.user_id).where(UserRole.role_id.in_(role_ids)).distinct()
        ).scalars().all()

        if not recipient_user_ids:
            logger.warning("No report recipients found — skipping email dispatch")
            return {"tickets": len(tickets), "recipients": 0, "emailed": False}

        # INTEGRATION POINT: Cognito ListUsers to convert user_ids to email addresses
        # from ticketing.auth.cognito import get_user_emails
        # emails = get_user_emails(recipient_user_ids)
        # For proto: log and skip (email configured later)
        logger.info(
            "Quarterly report: %d tickets, %d recipients (email dispatch pending Cognito wiring)",
            len(tickets), len(recipient_user_ids),
        )

        # When Cognito is wired, uncomment:
        # filename = f"grm_report_{d_from}_{d_to}.xlsx"
        # send_email(
        #     to=emails,
        #     subject=f"GRM Quarterly Report {d_from} – {d_to}",
        #     body=(
        #         f"Please find attached the GRM quarterly report for period "
        #         f"{d_from} to {d_to}.\n\n"
        #         f"Total grievances in period: {len(tickets)}\n"
        #         "Generated automatically by the GRM Ticketing System."
        #     ),
        #     attachments=[{"filename": filename, "content_base64": ..., "content_type": "..."}],
        # )

        db.close()
        return {
            "tickets": len(tickets),
            "recipients": len(recipient_user_ids),
            "date_from": str(d_from),
            "date_to": str(d_to),
            "emailed": False,  # True once Cognito integration is wired
        }

    except Exception as exc:
        logger.exception("dispatch_quarterly_report error: %s", exc)
        raise self.retry(exc=exc)
    finally:
        db.close()
