"""required_slots routing for validate_form_contact."""

from __future__ import annotations

from typing import List, Text

from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict


def contact_required_slots(tracker: Tracker) -> List[Text]:
    story_main = tracker.get_slot("story_main")
    sensitive_issues_follow_up = tracker.get_slot("sensitive_issues_follow_up")
    seah_focal_stage = tracker.get_slot("seah_focal_stage")
    seah_role = tracker.get_slot("seah_victim_survivor_role")

    required_slots_location = [
        "complainant_location_consent",
        "complainant_province",
        "complainant_district",
        "complainant_municipality_temp",
        "complainant_municipality_confirmed",
        "complainant_village_temp",
        "complainant_village_confirmed",
        "complainant_ward",
        "complainant_address_temp",
        "complainant_address_confirmed",
        "complainant_address",
    ]
    required_slots_location_seah = [
        "complainant_province",
        "complainant_district",
        "complainant_municipality_temp",
        "complainant_municipality_confirmed",
    ]
    required_slots_location_seah_municipality_only = [
        "complainant_province",
        "complainant_district",
        "complainant_municipality_temp",
        "complainant_municipality_confirmed",
    ]
    required_slots_contact = [
        "complainant_consent",
        "complainant_full_name",
        "complainant_email_temp",
        "complainant_email_confirmed",
    ]

    if story_main == "seah_intake" and seah_focal_stage == "bootstrap_reporter_contact":
        return ["complainant_full_name"]

    if story_main == "seah_intake" and seah_focal_stage == "complainant_contact":
        return []

    if story_main == "seah_intake" and sensitive_issues_follow_up == "anonymous":
        if seah_role in {"victim_survivor", "not_victim_survivor"}:
            return required_slots_location_seah_municipality_only
        return required_slots_location_seah

    if story_main == "seah_intake":
        if seah_role in {"victim_survivor", "not_victim_survivor"}:
            return required_slots_location_seah_municipality_only + required_slots_contact
        return required_slots_location_seah + required_slots_contact

    return required_slots_location + required_slots_contact
