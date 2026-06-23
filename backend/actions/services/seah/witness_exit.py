"""Support-service messaging when a SEAH witness exits without filing."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from rasa_sdk import Tracker

from backend.shared_functions.seah_service_providers import (
    format_details_utterance,
    format_recommendation_utterance,
)

_THANK_YOU_EN = (
    "Thank you. Here are the potential support services that can help the victim-survivor:"
)
_THANK_YOU_NE = (
    "धन्यवाद। यहाँ पीडित/उत्तरजीवीलाई सहयोग गर्न सक्ने सम्भावित सहयोग सेवाहरू छन्:"
)


def has_location_context(tracker: Tracker) -> bool:
    """True when any complainant or canonical location slot is populated."""
    keys = (
        "complainant_province",
        "complainant_district",
        "complainant_municipality",
        "location_code",
        "level_1_code",
        "level_2_code",
        "level_3_code",
    )
    return any(tracker.get_slot(key) for key in keys)


def build_witness_exit_support_message(
    language_code: str,
    providers: List[Dict[str, Any]],
    *,
    municipality: Optional[str] = None,
    district: Optional[str] = None,
) -> str:
    """Thank-you line plus location-aware centre recommendation and contact details."""
    intro = _THANK_YOU_NE if language_code == "ne" else _THANK_YOU_EN
    recommendation = format_recommendation_utterance(
        providers,
        language_code,
        municipality=municipality,
        district=district,
    )
    parts = [intro, recommendation]
    if providers:
        details = format_details_utterance(providers, language_code)
        if details:
            parts.append(details)
    return "\n\n".join(parts)


def build_witness_exit_no_location_message(language_code: str) -> str:
    """Fallback when no location context is available yet."""
    if language_code == "ne":
        return (
            "धन्यवाद। थप सहयोगका लागि https://nwchelpline.gov.np मा सम्पर्क गर्नुहोस्।"
        )
    return "Thank you. For further support, contact https://nwchelpline.gov.np."
