"""Detect en/ne for location validation (lightweight; not Facebook fastText)."""

from __future__ import annotations

import re
from typing import List, Optional

_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
_SUPPORTED = frozenset({"en", "ne"})


def detect_app_language(text: Optional[str], fallback: str = "en") -> str:
    """
    Return ``en`` or ``ne`` for ticketing location trees.

    Devanagari script → Nepali immediately (reliable for admin names).
    Otherwise ``langdetect`` (Google's port — small, no model download).
    """
    fb = fallback if fallback in _SUPPORTED else "en"
    if not text or not str(text).strip():
        return fb

    cleaned = str(text).strip()
    if _DEVANAGARI_RE.search(cleaned):
        return "ne"

    try:
        from langdetect import LangDetectException, detect

        if detect(cleaned) == "ne":
            return "ne"
    except LangDetectException:
        pass
    except Exception:
        pass

    return "en"


def language_candidates(text: Optional[str], fallback: str = "en") -> List[str]:
    """Primary detected language first, then the other tree (for mixed input)."""
    primary = detect_app_language(text, fallback)
    secondary = "ne" if primary == "en" else "en"
    out: List[str] = []
    for lang in (primary, secondary):
        if lang not in out:
            out.append(lang)
    return out
