"""Intake routes (chatbot story_main) and seed defaults for project workflow routing."""
from __future__ import annotations

# Canonical values — match chatbot story_main slot.
INTAKE_ROUTE_NEW_GRIEVANCE = "new_grievance"
INTAKE_ROUTE_SEAH = "seah_intake"
INTAKE_ROUTE_ROAD_HAZARD = "road_hazard_grievance"

ACTIVE_INTAKE_ROUTES = frozenset({
    INTAKE_ROUTE_NEW_GRIEVANCE,
    INTAKE_ROUTE_SEAH,
    INTAKE_ROUTE_ROAD_HAZARD,
})

INTAKE_ROUTE_CATALOG: list[dict[str, str]] = [
    {"key": INTAKE_ROUTE_NEW_GRIEVANCE, "label": "File a grievance (safeguards GRM)"},
    {"key": INTAKE_ROUTE_ROAD_HAZARD, "label": "Report a road hazard (fast path)"},
    {"key": INTAKE_ROUTE_SEAH, "label": "SEAH intake"},
]

# Tie-break when categories imply multiple routes (lower = wins).
INTAKE_ROUTE_PRIORITY: dict[str, int] = {
    INTAKE_ROUTE_SEAH: 0,
    INTAKE_ROUTE_ROAD_HAZARD: 1,
    INTAKE_ROUTE_NEW_GRIEVANCE: 2,
}

_LEGACY_INTAKE_ALIASES: dict[str, str] = {
    "grievance_new": INTAKE_ROUTE_NEW_GRIEVANCE,
    "standard_grievance": INTAKE_ROUTE_NEW_GRIEVANCE,
    "grievance_submission": INTAKE_ROUTE_NEW_GRIEVANCE,
    "seah": INTAKE_ROUTE_SEAH,
    "dust": INTAKE_ROUTE_ROAD_HAZARD,
    "dust_grievance": INTAKE_ROUTE_ROAD_HAZARD,
    "fast_track": INTAKE_ROUTE_ROAD_HAZARD,
    "road_hazard": INTAKE_ROUTE_ROAD_HAZARD,
}

SEED_ROAD_HAZARD_CLASSIFICATIONS = ["Road Hazard"]
SEED_SEAH_CLASSIFICATIONS = [
    "Gender",
    "Gender, Social",
    "Malicious Behavior",
    "Malicious Behavior, Environmental",
]

SEED_ROAD_HAZARD_INTAKE_ROUTE = INTAKE_ROUTE_ROAD_HAZARD
SEED_SEAH_INTAKE_ROUTE = INTAKE_ROUTE_SEAH
SEED_SAFEGUARDS_INTAKE_ROUTE = INTAKE_ROUTE_NEW_GRIEVANCE


def normalize_classification(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def normalize_intake_route(value: str | None) -> str | None:
    """Map webhook / legacy values to canonical story_main intake_route."""
    if value is None:
        return None
    key = str(value).strip().lower()
    if not key:
        return None
    if key in ACTIVE_INTAKE_ROUTES:
        return key
    return _LEGACY_INTAKE_ALIASES.get(key)


def intake_route_from_payload(
    *,
    intake_route: str | None = None,
    legacy_is_seah: bool = False,
) -> str | None:
    """Build canonical intake_route from webhook fields."""
    route = normalize_intake_route(intake_route)
    if route:
        return route
    if legacy_is_seah:
        return INTAKE_ROUTE_SEAH
    return None
