"""
GRM Ticketing Celery application instance.

Separate from the existing `backend.task_queue.celery_app` — same Redis broker,
different app name and queue so workers don't pick up each other's tasks.

Broker:  CELERY_BROKER_URL   (default redis://localhost:6379/1)
Backend: CELERY_RESULT_BACKEND (default redis://localhost:6379/2)
Queue:   grm_ticketing
"""
import logging

from celery import Celery
from celery.schedules import crontab
from celery.signals import task_failure

from ticketing.config.settings import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

celery_app = Celery(
    "grm_ticketing",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "ticketing.tasks.escalation",
        "ticketing.tasks.notifications",
        "ticketing.tasks.reports",
        "ticketing.tasks.grievance_sync",
        "ticketing.tasks.llm",
        "ticketing.tasks.archiving",
        "ticketing.tasks.location_geocode",
        "ticketing.tasks.ops_heartbeat",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Use a dedicated queue — does not interfere with existing chatbot workers
    task_default_queue="grm_ticketing",
    task_routes={
        "ticketing.tasks.escalation.*": {"queue": "grm_ticketing"},
        "ticketing.tasks.notifications.*": {"queue": "grm_ticketing"},
        "ticketing.tasks.reports.*": {"queue": "grm_ticketing"},
        "ticketing.tasks.grievance_sync.*": {"queue": "grm_ticketing"},
        "ticketing.tasks.llm.*": {"queue": "grm_ticketing"},
        "ticketing.tasks.archiving.*": {"queue": "grm_ticketing"},
        "ticketing.tasks.location_geocode.*": {"queue": "grm_geocode"},
        "ticketing.tasks.ops_heartbeat.*": {"queue": "grm_ticketing"},
    },
    # ── Beat schedule ──────────────────────────────────────────────────────────
    beat_schedule={
        # Beat liveness heartbeat — every minute; ops monitor reads health:beat:last_run
        "grm-beat-heartbeat": {
            "task": "ticketing.tasks.ops_heartbeat.beat_heartbeat",
            "schedule": 60,
        },
        # Grievance sync: polls public.grievances for new submissions every 2 minutes
        # Creates ticketing.tickets automatically — no chatbot code change needed
        "grm-grievance-sync": {
            "task": "ticketing.tasks.grievance_sync.sync_grievances",
            "schedule": 120,  # 2 minutes
        },
        # SLA watchdog: runs every 15 minutes
        "grm-sla-watchdog": {
            "task": "ticketing.tasks.escalation.check_sla_watchdog",
            "schedule": 60 * 15,  # 900 seconds
        },
        # Quarterly reports: 5th of January, April, July, October at 06:00 UTC
        "grm-quarterly-report": {
            "task": "ticketing.tasks.reports.dispatch_quarterly_report",
            "schedule": crontab(
                hour=6,
                minute=0,
                day_of_month=5,
                month_of_year="1,4,7,10",
            ),
        },
        # Archive eligible resolved cases — daily 03:00 Asia/Kathmandu (21:15 UTC)
        "grm-archive-eligible": {
            "task": "ticketing.tasks.archiving.archive_eligible_grievances_task",
            "schedule": crontab(hour=21, minute=15),
        },
    },
)


@task_failure.connect
def _on_grm_task_failure(sender=None, task_id=None, exception=None, **kwargs):
    """Immediate deduped alert on any GRM business-task failure (spec 11 §5.3).

    Uses the ops alerting path (HTTP Messaging API). The heartbeat task is excluded
    to avoid noise (its failure is surfaced by grm_beat_liveness_check instead).
    """
    task_name = getattr(sender, "name", str(sender))
    if task_name and task_name.endswith("ops_heartbeat.beat_heartbeat"):
        return
    try:
        from ops.alerts import send_alert

        send_alert(
            signature=f"grm_task_failure:{task_name}",
            subject=f"GRM task failed: {task_name}",
            body_html=(
                f"<p>Celery task <b>{task_name}</b> failed.</p>"
                f"<p>task_id: {task_id}</p><pre>{exception}</pre>"
            ),
        )
    except Exception as exc:  # pragma: no cover - alerting must never crash the worker
        logger.error("task_failure alert hook error: %s", exc)
