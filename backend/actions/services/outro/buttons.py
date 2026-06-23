"""Pure button-assembly helpers for grievance/SEAH outro actions.

Extracted from ``backend.actions.action_outro`` so the Rasa actions keep only
their dispatch flow. Pure with respect to the static button catalog.
"""

from __future__ import annotations

from typing import Dict, List

from backend.actions.utils.mapping_buttons import (
    BUTTONS_CLOSE_SESSION_ONLY,
    BUTTONS_FILE_ANOTHER_GRIEVANCE,
)


def post_submit_buttons(language_code: str) -> List[Dict[str, str]]:
    """Close-session + file-another-grievance buttons, language-aware (en fallback)."""
    lang = language_code if language_code in BUTTONS_CLOSE_SESSION_ONLY else "en"
    buttons = list(BUTTONS_CLOSE_SESSION_ONLY.get(lang, BUTTONS_CLOSE_SESSION_ONLY["en"]))
    buttons.extend(BUTTONS_FILE_ANOTHER_GRIEVANCE.get(lang, BUTTONS_FILE_ANOTHER_GRIEVANCE["en"]))
    return buttons
