# SPDX-License-Identifier: Apache-2.0

"""Resolution note rules, the per-workflow action limit, and the starter actions (spec 08 §2.2).

The actions themselves live in the ``ticketing.resolution_actions`` catalog (GRM-116). Migration
``b3d5f7h9`` seeds the starter actions on a database that already has a ministry, from its own frozen
copy; :data:`STARTER_ACTIONS` is what the seed scripts use on a database that does not yet.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

RESOLUTION_MIN_NOTE_LEN = 12

# At most this many actions per workflow and per template (owner's rule, Q-10). A constant, not a
# setting: an officer chooses from a short list, often on a phone, in a second language — and a list
# that cannot pass 8 cannot fill up with near-duplicates. Enforced in set_workflow_actions.
MAX_RESOLUTION_ACTIONS = 8

# Today's five — codes unchanged since before the catalog, so every historical event still resolves.
GENERAL_ACTION_CODES: tuple[str, ...] = (
    "CLASSIFIED",
    "DEMAND_REJECTED",
    "ACCEPTED_MONETARY",
    "ACCEPTED_RELOCATION",
    "ACCEPTED_OTHER",
)

# For a workflow bound to the road-hazard chatbot menu.
ROAD_WORKS_ACTION_CODES: tuple[str, ...] = (
    "ROAD_REPAIRED",
    "ROAD_MADE_SAFE",
    "ROAD_DUST_NOISE_CONTROLLED",
    "ROAD_NOT_PROJECT_ROAD",
    "ROAD_NO_HAZARD_FOUND",
)

# (code, label, default wording) — shared actions of the ministry that owns them.
STARTER_ACTIONS: tuple[tuple[str, str, str], ...] = (
    ("CLASSIFIED", "Grievance classified",
     "This grievance has been reviewed and classified. No specific remedial action is required "
     "beyond continued monitoring under the project GRM procedure."),
    ("DEMAND_REJECTED", "Complainant demand rejected",
     "After investigation, the grievance was found not to be substantiated. The complainant's "
     "request is not accepted. The case is closed with this determination."),
    ("ACCEPTED_MONETARY", "Grievance accepted — monetary compensation",
     "The grievance is substantiated. Remedial action includes monetary compensation as agreed "
     "with the complainant / per contract and GRM procedure."),
    ("ACCEPTED_RELOCATION", "Grievance accepted — relocation",
     "The grievance is substantiated. Remedial action includes relocation / resettlement support "
     "as applicable under project safeguards."),
    ("ACCEPTED_OTHER", "Grievance accepted — other remedy",
     "The grievance is substantiated. Remedial action has been agreed (other than monetary "
     "compensation or relocation). Details are recorded below."),
    ("ROAD_REPAIRED", "Hazard repaired",
     "The reported hazard was inspected and repaired."),
    ("ROAD_MADE_SAFE", "Made safe — signs, barriers or traffic control",
     "The site was made safe with warning signs, barriers or traffic control. A permanent repair "
     "is planned."),
    ("ROAD_DUST_NOISE_CONTROLLED", "Dust or noise controlled",
     "The contractor was instructed to control dust or noise, for example by spraying water or "
     "limiting working hours."),
    ("ROAD_NOT_PROJECT_ROAD", "Not on a project road — passed on",
     "The location is not on a project road. The report was passed to the authority responsible "
     "for it."),
    ("ROAD_NO_HAZARD_FOUND", "No hazard found on inspection",
     "The site was inspected and no hazard was found."),
)

# Preselected in the resolve form when a workflow offers it (the pre-catalog default).
PREFERRED_DEFAULT_ACTION_CODE = "ACCEPTED_OTHER"


def validate_resolution_note(note: Optional[str]) -> str:
    text = (note or "").strip()
    if len(text) < RESOLUTION_MIN_NOTE_LEN:
        raise ValueError(
            f"Resolution text must be at least {RESOLUTION_MIN_NOTE_LEN} characters."
        )
    return text


def format_resolution_note(
    action_label: Optional[str], officer_text: str, *, at: Optional[datetime] = None
) -> str:
    """The thread bubble body. ``action_label`` is None for a case in a sensitive workflow,
    which records no action (DESIGN §3.1.3) — the heading then names no outcome."""
    when = (at or datetime.now(timezone.utc)).strftime("%Y-%m-%d")
    heading = f"Resolution — {action_label}" if action_label else "Resolution"
    return f"{heading}\nDate: {when}\n\n{officer_text.strip()}"
