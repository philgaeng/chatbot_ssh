"""Merge SEAH contact-provided and party payload slots during contact intake."""

from __future__ import annotations

from typing import Any, Dict

from backend.actions.services.seah import contact_channels as seah_channels
from backend.actions.services.seah import party_payload as seah_party


def merge_seah_contact_and_party_slots(
    story_main: Any,
    current_slots: Dict[str, Any],
    partial: Dict[str, Any],
    *,
    helpers: Any,
    default_values: Dict[str, Any],
) -> Dict[str, Any]:
    merged = seah_channels.seah_contact_provided_update(
        story_main, current_slots, partial, helpers
    )
    merged.update(
        seah_party.upsert_active_party_payload(
            current_slots, partial, default_values=default_values
        )
    )
    return merged
