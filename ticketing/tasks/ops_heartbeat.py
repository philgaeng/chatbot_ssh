"""
GRM beat liveness heartbeat.

Writes a Redis key every minute so the ops monitor's grm_beat_liveness_check can
detect a dead/stuck Celery Beat. Intentionally tiny and dependency-free beyond
the Redis the beat already uses.

Key:  health:beat:last_run  (Redis db 0, TTL 180s)
Read by: ops/checks.py::grm_beat_liveness_check
"""
from __future__ import annotations

import datetime as dt
import logging

import redis

from ticketing.config.settings import get_settings
from ticketing.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

BEAT_HEARTBEAT_KEY = "health:beat:last_run"


def _heartbeat_redis_url() -> str:
    """Use db 0 of the same Redis host as the broker (ops monitor reads db 0)."""
    broker = get_settings().celery_broker_url
    base, _, _db = broker.rpartition("/")
    return f"{base}/0" if base else broker


@celery_app.task(name="ticketing.tasks.ops_heartbeat.beat_heartbeat")
def beat_heartbeat() -> str:
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    try:
        r = redis.from_url(_heartbeat_redis_url(), socket_timeout=3, socket_connect_timeout=3)
        r.set(BEAT_HEARTBEAT_KEY, now, ex=180)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("beat_heartbeat write failed: %s", exc)
    return now
