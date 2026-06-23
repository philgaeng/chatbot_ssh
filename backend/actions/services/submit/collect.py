"""Collect and enrich grievance payload from tracker slots."""

from __future__ import annotations

import logging
from typing import Any, Dict

from rasa_sdk import Tracker

from backend.actions.services.submit import classification as submit_classification
from backend.actions.services.submit import storage as submit_storage
from backend.shared_functions.geo_pin import (
    apply_location_enrichment_for_submit,
    slots_for_location_resolve,
)
from backend.shared_functions.location_mapping import resolve_location_payload

logger = logging.getLogger(__name__)

_SUBMIT_KEYS = [
    "complainant_id",
    "complainant_phone",
    "complainant_email",
    "complainant_full_name",
    "complainant_gender",
    "complainant_province",
    "complainant_district",
    "complainant_municipality",
    "complainant_village",
    "complainant_address",
    "grievance_id",
    "grievance_description",
    "otp_verified",
    "active_party_role",
    "party_contacts",
    "party_victim_survivor",
    "party_witness",
    "party_relative",
    "party_seah_focal_point",
    "party_other_reporter",
]

_REVIEW_KEYS = [
    "grievance_categories",
    "grievance_summary",
    "grievance_sensitive_issue",
    "grievance_classification_status",
]


def collect_grievance_data(
    tracker: Tracker,
    *,
    db_manager: Any,
    helpers_repo: Any,
    grievance_status_submitted: str,
    skip_value: str,
    not_provided: str,
    llm_classification_enabled: bool,
    grievance_classification_status: Dict[str, str],
    review: bool = False,
    check_high_priority,
) -> Dict[str, Any]:
    keys = list(_SUBMIT_KEYS)
    if review:
        keys.extend(_REVIEW_KEYS)

    grievance_data = {k: tracker.get_slot(k) for k in keys}
    location_payload = resolve_location_payload(
        db_manager=db_manager,
        slots=slots_for_location_resolve(grievance_data),
        country_code=tracker.get_slot("country_code") or "NP",
    )
    grievance_data.update(location_payload)
    grievance_data.update(
        apply_location_enrichment_for_submit(
            grievance_data,
            geo_lat=tracker.get_slot("geo_lat"),
            geo_lng=tracker.get_slot("geo_lng"),
            location_pin_status=tracker.get_slot("location_pin_status"),
            location_code=tracker.get_slot("location_code")
            or location_payload.get("location_code"),
        )
    )
    logger.info(
        "submission_location_resolution country_code=%s status=%s deepest_level=%s",
        location_payload.get("country_code"),
        location_payload.get("location_resolution_status"),
        location_payload.get("location_deepest_mapped_level", 0),
    )

    grievance_timestamp = helpers_repo.get_current_datetime()
    grievance_data["grievance_status"] = grievance_status_submitted
    if review:
        grievance_data["grievance_high_priority"] = check_high_priority(
            grievance_data.get("grievance_categories")
        )

    grievance_data["grievance_timeline"] = helpers_repo.get_timeline_by_status_code(
        status_update_code=grievance_status_submitted,
        grievance_high_priority=grievance_data.get("grievance_high_priority", False),
        sensitive_issues_detected=grievance_data.get("grievance_sensitive_issue", False),
    )
    grievance_data["submission_type"] = "new_grievance"
    grievance_data["grievance_timestamp"] = grievance_timestamp
    grievance_data = submit_storage.normalize_skip_and_null_for_db(
        grievance_data, skip_value=skip_value, not_provided=not_provided
    )
    if grievance_data.get("party_contacts") == not_provided:
        grievance_data["party_contacts"] = {}
    grievance_data["grievance_classification_status"] = (
        submit_classification.classification_status_for_submit(
            tracker,
            grievance_data,
            db_manager=db_manager,
            skip_value=skip_value,
            not_provided=not_provided,
            llm_classification_enabled=llm_classification_enabled,
            grievance_classification_status=grievance_classification_status,
        )
    )
    logger.info("Grievance data collected: keys=%s", sorted(grievance_data.keys()))
    return grievance_data
