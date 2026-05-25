"""Resolution categories and note formatting (spec §2.2)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

RESOLUTION_MIN_NOTE_LEN = 12

RESOLUTION_CATEGORIES: dict[str, dict[str, str]] = {
    "CLASSIFIED": {
        "label": "Grievance classified",
        "default_wording": (
            "This grievance has been reviewed and classified. "
            "No specific remedial action is required beyond continued monitoring "
            "under the project GRM procedure."
        ),
    },
    "DEMAND_REJECTED": {
        "label": "Complainant demand rejected",
        "default_wording": (
            "After investigation, the grievance was found not to be substantiated. "
            "The complainant's request is not accepted. The case is closed with this determination."
        ),
    },
    "ACCEPTED_MONETARY": {
        "label": "Grievance accepted — monetary compensation",
        "default_wording": (
            "The grievance is substantiated. Remedial action includes monetary compensation "
            "as agreed with the complainant / per contract and GRM procedure."
        ),
    },
    "ACCEPTED_RELOCATION": {
        "label": "Grievance accepted — relocation",
        "default_wording": (
            "The grievance is substantiated. Remedial action includes relocation / "
            "resettlement support as applicable under project safeguards."
        ),
    },
    "ACCEPTED_OTHER": {
        "label": "Grievance accepted — other remedy",
        "default_wording": (
            "The grievance is substantiated. Remedial action has been agreed "
            "(other than monetary compensation or relocation). Details are recorded below."
        ),
    },
}


def resolution_category_label(code: str) -> str:
    return RESOLUTION_CATEGORIES.get(code, {}).get("label", code)


def validate_resolution_category(code: Optional[str]) -> str:
    if not code or code not in RESOLUTION_CATEGORIES:
        valid = ", ".join(sorted(RESOLUTION_CATEGORIES))
        raise ValueError(f"resolution_category must be one of: {valid}")
    return code


def validate_resolution_note(note: Optional[str]) -> str:
    text = (note or "").strip()
    if len(text) < RESOLUTION_MIN_NOTE_LEN:
        raise ValueError(
            f"Resolution text must be at least {RESOLUTION_MIN_NOTE_LEN} characters."
        )
    return text


def format_resolution_note(category: str, officer_text: str, *, at: Optional[datetime] = None) -> str:
    when = (at or datetime.now(timezone.utc)).strftime("%Y-%m-%d")
    label = resolution_category_label(category)
    return f"Resolution — {label}\nDate: {when}\n\n{officer_text.strip()}"
