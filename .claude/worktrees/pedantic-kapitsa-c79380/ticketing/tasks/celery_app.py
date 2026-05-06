"""
GRM Ticketing Celery application instance.

Separate from the existing `backend.task_queue.celery_app` — same Redis broker,
different app name and queue so workers don't pick up each other's tasks.

Broker:  CELERY_BROKER_URL   (default redis://localhost:6379/1)
Backend: CELERY_RESULT_BACKEND (default redis://localhost:6379/2)
Queue:   grm_ticketing
"""
from celery import Celery
from celery.schedules import crontab

from ticketing.config.settings import get_settings

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
    },
    # ── Beat schedule ──────────────────────────────────────────────────────────
    beat_schedule={
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
    },
)
