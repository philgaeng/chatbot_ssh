"""
LLM client for the ticketing service.

Uses OpenAI gpt-4 — same provider as the chatbot backend (backend/services/LLM_services.py).
DO NOT import from backend/services/ — keep ticketing independent. Replicate the pattern here.

API key: OPENAI_API_KEY in env.local (already present, used by chatbot).
Init: get_settings().openai_api_key
"""

import logging
import re
from typing import Optional

from openai import OpenAI

from ticketing.config.settings import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level client (lazy-init — avoids import-time errors if key is absent)
# ---------------------------------------------------------------------------
_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    """Return a cached OpenAI client, initialising on first call."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = OpenAI(
            api_key=settings.openai_api_key,
            timeout=30.0,
        )
    return _client


# ---------------------------------------------------------------------------
# Translation helper
# ---------------------------------------------------------------------------

_TRANSLATE_SYSTEM = (
    "You are a professional translator. "
    "Translate the following text to English. "
    "If the text is already in English, return it as-is. "
    "Preserve technical, legal, and proper-noun terms exactly. "
    "Output only the translated text — no commentary, no quotation marks."
)

_LANG_RE = re.compile(
    r"[ऀ-ॿঀ-৿਀-੿઀-૿"
    r"଀-୿஀-௿ఀ-౿ಀ-೿"
    r"ഀ-ൿऀ-ॿ]"  # Devanagari + other Indic scripts
)


def _looks_non_english(text: str) -> bool:
    """
    Cheap heuristic: if >5% of characters are non-ASCII / Indic script,
    assume the text needs translation.  Avoids unnecessary API calls for
    English-only notes.
    """
    if not text:
        return False
    non_ascii = sum(1 for c in text if ord(c) > 127)
    return (non_ascii / len(text)) > 0.05


def translate_to_english(text: str) -> Optional[str]:
    """
    Translate *text* to English using gpt-4.

    Returns the translated string, or None on error (caller logs and skips).
    If the text already looks like English, returns it unchanged without an API call.
    """
    if not text or not text.strip():
        return None

    if not _looks_non_english(text):
        logger.debug("translate_to_english: text looks English, skipping API call")
        return text

    client = _get_client()
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": _TRANSLATE_SYSTEM},
                {"role": "user", "content": text},
            ],
            temperature=0.2,
            max_tokens=1024,
        )
        translated = response.choices[0].message.content or ""
        return translated.strip() or None
    except Exception as exc:
        logger.error("translate_to_english failed: %s", exc, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Findings / summary helper
# ---------------------------------------------------------------------------

_FINDINGS_SYSTEM = (
    "You are a grievance redress officer writing an internal case summary. "
    "Summarise the following case notes and key events into a brief Findings report. "
    "Include: key facts, actions taken, outstanding issues, and recommended next step. "
    "Write in formal English. Maximum 150 words. "
    "Output only the findings text — no headings, no bullet lists, just a concise paragraph."
)


def generate_case_findings(case_text: str) -> Optional[str]:
    """
    Generate a case-findings summary over all key events and notes for a ticket.

    *case_text* is a pre-formatted multi-line string with one event per line.
    Returns the findings paragraph, or None on error.
    """
    if not case_text or not case_text.strip():
        return None

    client = _get_client()
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": _FINDINGS_SYSTEM},
                {"role": "user", "content": case_text},
            ],
            temperature=0.3,
            max_tokens=300,
        )
        findings = response.choices[0].message.content or ""
        return findings.strip() or None
    except Exception as exc:
        logger.error("generate_case_findings failed: %s", exc, exc_info=True)
        return None
