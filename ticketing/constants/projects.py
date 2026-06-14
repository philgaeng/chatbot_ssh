"""Stable project identifiers and legacy chatbot code aliases."""

from __future__ import annotations

# Seeded in ticketing.migrations e8d4b6a0f291 — stable across short_code renames.
KL_ROAD_PROJECT_ID = "7b0c4f10-grm-klrd-0000-000000000001"

# Chatbot slots / webhook payloads may still send legacy codes after admin renames.
# Resolution order in project_routing: project_id → short_code → this map.
CHATBOT_LEGACY_PROJECT_CODES: dict[str, str] = {
    "KL_ROAD": KL_ROAD_PROJECT_ID,
}


def legacy_project_id_for_code(code: str | None) -> str | None:
    if not code:
        return None
    return CHATBOT_LEGACY_PROJECT_CODES.get(code.strip().upper())
