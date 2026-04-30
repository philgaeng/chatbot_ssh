"""
GRM Ticketing — Celery application.

Separate Celery app (name: grm_ticketing) to avoid conflicts with the
existing chatbot Celery workers (backend.task_queue.celery_app).

Start worker:
  celery -A ticketing.tasks worker -Q grm_ticketing -l info

Start beat scheduler:
  celery -A ticketing.tasks beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
  # OR simple file scheduler for proto:
  celery -A ticketing.tasks beat -l info
"""
from ticketing.tasks.celery_app import celery_app

# Register task modules so beat and workers can discover them
import ticketing.tasks.escalation   # noqa: F401 — registers tasks
import ticketing.tasks.notifications  # noqa: F401
import ticketing.tasks.reports       # noqa: F401

__all__ = ["celery_app"]
