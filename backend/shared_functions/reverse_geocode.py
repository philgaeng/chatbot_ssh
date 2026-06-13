"""Reverse geocoding for map pins via OSM Nominatim (CB-06 async enrichment)."""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)

NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
DEFAULT_USER_AGENT = "nepal-grm-chatbot/1.0 (map-pin-geocode; dev@facets-ai.com)"
# Admin-level detail (city / municipality), not street-level.
NOMINATIM_ADMIN_ZOOM = 10
MIN_REQUEST_INTERVAL_SEC = 1.05
_REDIS_LOCK_KEY = "nominatim:geocode:mutex"
_REDIS_LAST_CALL_KEY = "nominatim:geocode:last_call"


class NominatimError(Exception):
    """Base error for Nominatim reverse geocode failures."""


class NominatimRateLimitError(NominatimError):
    """HTTP 429 or policy rate limit — safe to retry later."""


class NominatimUnavailableError(NominatimError):
    """Transient upstream failure — safe to retry later."""


def _user_agent() -> str:
    return (os.getenv("NOMINATIM_USER_AGENT") or DEFAULT_USER_AGENT).strip()


def parse_nominatim_admin_address(address: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """
    Map Nominatim address keys to Nepal admin hierarchy labels.

    At zoom=10 for NP, Nominatim typically returns:
      state → province, county → district, city|municipality → municipality.
    """
    if not address:
        return {"province": None, "district": None, "municipality": None}

    municipality = (
        address.get("city")
        or address.get("municipality")
        or address.get("town")
        or address.get("village")
    )
    return {
        "province": _clean_label(address.get("state")),
        "district": _clean_label(address.get("county")),
        "municipality": _clean_label(municipality),
    }


def _clean_label(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _redis_client():
    import redis

    url = (
        os.getenv("CELERY_BROKER_URL")
        or os.getenv("REDIS_URL")
        or "redis://localhost:6379/1"
    )
    return redis.from_url(url)


def wait_for_nominatim_rate_limit(
    *,
    min_interval: float = MIN_REQUEST_INTERVAL_SEC,
    lock_timeout: float = 45.0,
    blocking_timeout: float = 120.0,
) -> None:
    """
    Global 1 req/s guard shared across Celery workers (Nominatim policy).

    Uses a Redis mutex + last-call timestamp on the Celery broker Redis.
    Reserves the slot at call start so concurrent workers cannot overlap requests.
    """
    try:
        client = _redis_client()
    except Exception as exc:
        logger.warning("Nominatim rate limiter unavailable (%s); sleeping %.2fs", exc, min_interval)
        time.sleep(min_interval)
        return

    lock = client.lock(_REDIS_LOCK_KEY, timeout=int(lock_timeout), blocking_timeout=int(blocking_timeout))
    acquired = lock.acquire(blocking=True)
    if not acquired:
        raise NominatimUnavailableError("Could not acquire Nominatim rate-limit lock")

    try:
        now = time.time()
        raw_last = client.get(_REDIS_LAST_CALL_KEY)
        last = float(raw_last) if raw_last else 0.0
        wait = min_interval - (now - last)
        if wait > 0:
            time.sleep(wait)
        client.set(_REDIS_LAST_CALL_KEY, str(time.time()))
    finally:
        lock.release()


def nominatim_reverse_geocode(
    lat: float,
    lng: float,
    *,
    lang_code: str = "en",
    zoom: int = NOMINATIM_ADMIN_ZOOM,
    respect_rate_limit: bool = True,
    timeout: float = 20.0,
) -> Dict[str, Optional[str]]:
    """
    Reverse geocode coordinates to province / district / municipality names.

    Returns dict with keys province, district, municipality (values may be None).
    Raises NominatimRateLimitError / NominatimUnavailableError on retryable failures.
    """
    if respect_rate_limit:
        wait_for_nominatim_rate_limit()

    params = {
        "format": "jsonv2",
        "lat": f"{float(lat):.6f}",
        "lon": f"{float(lng):.6f}",
        "zoom": str(int(zoom)),
        "addressdetails": "1",
    }
    headers = {
        "User-Agent": _user_agent(),
        "Accept-Language": lang_code if lang_code in ("en", "ne") else "en",
    }
    url = f"{NOMINATIM_REVERSE_URL}?{urlencode(params)}"

    try:
        response = httpx.get(url, headers=headers, timeout=timeout)
    except httpx.TimeoutException as exc:
        raise NominatimUnavailableError(f"Nominatim timeout: {exc}") from exc
    except httpx.HTTPError as exc:
        raise NominatimUnavailableError(f"Nominatim HTTP error: {exc}") from exc

    if response.status_code == 429:
        raise NominatimRateLimitError("Nominatim HTTP 429")
    if response.status_code >= 500:
        raise NominatimUnavailableError(f"Nominatim HTTP {response.status_code}")
    if response.status_code != 200:
        raise NominatimError(f"Nominatim HTTP {response.status_code}: {response.text[:200]}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise NominatimError("Invalid Nominatim JSON") from exc

    address = payload.get("address") if isinstance(payload, dict) else None
    if not isinstance(address, dict):
        return {"province": None, "district": None, "municipality": None}

    return parse_nominatim_admin_address(address)
