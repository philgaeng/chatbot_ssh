"""
Celery task: daily archive of eligible resolved grievances.

Beat schedule: 03:00 Asia/Kathmandu (21:15 UTC) — see celery_app.py.
"""
from __future__ import annotations

import logging

from ticketing.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="ticketing.tasks.archiving.archive_eligible_grievances_task",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    acks_late=True,
)
def archive_eligible_grievances_task(self) -> dict:
    from ticketing.models.base import SessionLocal
    from ticketing.services.archiving import run_archive_job

    logger.info("archive_eligible_grievances_task starting...")
    db = SessionLocal()
    try:
        summary = run_archive_job(db)
        return {
            "as_of": summary.as_of.isoformat(),
            "candidates": summary.candidates,
            "archived": summary.archived,
            "skipped": summary.skipped,
            "errors": summary.errors,
            "dry_run": summary.dry_run,
        }
    except Exception as exc:
        logger.exception("archive_eligible_grievances_task error: %s", exc)
        raise self.retry(exc=exc) from exc
    finally:
        db.close()
