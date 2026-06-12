"""Intake signals and seed defaults for project workflow routing."""
from __future__ import annotations

# Chatbot / webhook intake signals (match project_workflows.intake_routes).
INTAKE_ROUTE_FAST_TRACK = "fast_track"
INTAKE_ROUTE_ROAD_HAZARD = "road_hazard"
INTAKE_ROUTE_DUST = "dust"
INTAKE_ROUTE_SEAH = "seah_intake"
INTAKE_ROUTE_STANDARD = "standard_grievance"
INTAKE_ROUTE_GRIEVANCE_NEW = "grievance_new"
INTAKE_ROUTE_NEW_GRIEVANCE = "new_grievance"

INTAKE_ROUTE_CATALOG: list[dict[str, str]] = [
    {"key": INTAKE_ROUTE_FAST_TRACK, "label": "Fast track (road hazard menu)"},
    {"key": INTAKE_ROUTE_ROAD_HAZARD, "label": "Road hazard intake"},
    {"key": INTAKE_ROUTE_DUST, "label": "Legacy dust path"},
    {"key": INTAKE_ROUTE_SEAH, "label": "SEAH intake"},
    {"key": INTAKE_ROUTE_STANDARD, "label": "Standard new grievance"},
    {"key": INTAKE_ROUTE_GRIEVANCE_NEW, "label": "Grievance details (manual / LLM off)"},
    {"key": INTAKE_ROUTE_NEW_GRIEVANCE, "label": "New grievance story"},
]

# Seed bindings for construction_road (overwritable in admin UI).
SEED_ROAD_HAZARD_CLASSIFICATIONS = ["Road Hazard"]
SEED_SEAH_CLASSIFICATIONS = [
    "Gender",
    "Gender, Social",
    "Malicious Behavior",
    "Malicious Behavior, Environmental",
]

SEED_ROAD_HAZARD_INTAKE_ROUTES = [
    INTAKE_ROUTE_FAST_TRACK,
    INTAKE_ROUTE_ROAD_HAZARD,
    INTAKE_ROUTE_DUST,
]
SEED_SEAH_INTAKE_ROUTES = [INTAKE_ROUTE_SEAH]
SEED_SAFEGUARDS_INTAKE_ROUTES = [
    INTAKE_ROUTE_STANDARD,
    INTAKE_ROUTE_GRIEVANCE_NEW,
    INTAKE_ROUTE_NEW_GRIEVANCE,
]


def normalize_classification(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def intake_signals_from_payload(
    *,
    intake_route: str | None = None,
    intake_fast_path: str | None = None,
    legacy_is_seah: bool = False,
) -> set[str]:
    """Build intake signal set from webhook fields (chatbot may send subset)."""
    signals: set[str] = set()
    for raw in (intake_route, intake_fast_path):
        if not raw:
            continue
        key = raw.strip().lower()
        signals.add(key)
        if key in ("road_hazard", "dust", "road_hazard_grievance"):
            signals.add(INTAKE_ROUTE_FAST_TRACK)
            signals.add(INTAKE_ROUTE_ROAD_HAZARD)
        if key == "dust":
            signals.add(INTAKE_ROUTE_DUST)
        if key in ("seah_intake", "seah"):
            signals.add(INTAKE_ROUTE_SEAH)
        if key in ("new_grievance",):
            signals.add(INTAKE_ROUTE_NEW_GRIEVANCE)
            signals.add(INTAKE_ROUTE_STANDARD)
    if legacy_is_seah:
        signals.add(INTAKE_ROUTE_SEAH)
    return signals
