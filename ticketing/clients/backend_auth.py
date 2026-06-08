"""Shared API key for ticketing → chatbot backend HTTP calls."""
from __future__ import annotations

from ticketing.config.settings import get_settings


def service_integration_api_key() -> str:
    """
    x-api-key sent to chatbot backend (grievance/complainant PATCH, messaging).

    Canonical env var: TICKETING_SECRET_KEY (same as chatbot → ticketing webhook).
    MESSAGING_API_KEY is an optional legacy alias when TICKETING_SECRET_KEY is unset.
    """
    settings = get_settings()
    return (settings.ticketing_secret_key or settings.messaging_api_key or "").strip()
