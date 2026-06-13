"""
Celery task: async reverse geocode for map-pin submissions.

Low-priority queue (grm_geocode) with global Redis rate limit (1 req/s Nominatim policy).
Retries transient failures with backoff starting at 3 seconds.
"""

from __future__ import annotations

import logging
import random
import sys
from pathlib import Path

# Celery workers may inherit a host PYTHONPATH from env.local; ensure /app is importable.
_APP_ROOT = Path(__file__).resolve().parents[2]
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

from ticketing.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_RETRY_BASE_SEC = 3
_RETRY_MAX_SEC = 30


@celery_app.task(
    name="ticketing.tasks.location_geocode.reverse_geocode_map_pin",
    bind=True,
    max_retries=8,
    default_retry_delay=_RETRY_BASE_SEC,
    rate_limit="1/s",
    acks_late=True,
    queue="grm_geocode",
)
def reverse_geocode_map_pin(
    self,
    complainant_id: str,
    grievance_id: str,
    lat: float,
    lng: float,
    lang_code: str = "en",
) -> dict:
    """
    Reverse geocode map pin → municipality/district/province → update complainant row.

    Idempotent: skips when level-3 municipality is already stored.
    """
    from backend.services.database_services.postgres_services import db_manager
    from backend.shared_functions.map_pin_geocode import (
        apply_map_pin_geocode_to_db,
        is_retryable_geocode_error,
    )
    from backend.shared_functions.reverse_geocode import NominatimError

    try:
        result = apply_map_pin_geocode_to_db(
            db_manager,
            complainant_id=complainant_id,
            grievance_id=grievance_id,
            lat=float(lat),
            lng=float(lng),
            lang_code=lang_code or "en",
            respect_rate_limit=True,
        )
        logger.info(
            "reverse_geocode_map_pin done grievance_id=%s status=%s municipality=%s",
            grievance_id,
            result.get("status"),
            result.get("municipality"),
        )
        return result
    except NominatimError as exc:
        if is_retryable_geocode_error(exc) and self.request.retries < self.max_retries:
            countdown = min(
                _RETRY_MAX_SEC,
                _RETRY_BASE_SEC * (2 ** self.request.retries) + random.uniform(0, 1.5),
            )
            logger.warning(
                "reverse_geocode_map_pin retry grievance_id=%s attempt=%s in %.1fs: %s",
                grievance_id,
                self.request.retries + 1,
                countdown,
                exc,
            )
            raise self.retry(exc=exc, countdown=countdown)
        logger.error(
            "reverse_geocode_map_pin failed grievance_id=%s: %s",
            grievance_id,
            exc,
        )
        return {"status": "error", "error": str(exc)}
    except Exception as exc:
        logger.exception(
            "reverse_geocode_map_pin unexpected error grievance_id=%s",
            grievance_id,
        )
        if self.request.retries < self.max_retries:
            countdown = min(
                _RETRY_MAX_SEC,
                _RETRY_BASE_SEC * (2 ** self.request.retries) + random.uniform(0, 1.5),
            )
            raise self.retry(exc=exc, countdown=countdown)
        return {"status": "error", "error": str(exc)}
