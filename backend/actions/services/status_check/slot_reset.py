"""Flow-specific slot reset for status check / new grievance / OTP."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Text, Union

from rasa_sdk import Tracker
from rasa_sdk.events import SlotSet

logger = logging.getLogger(__name__)


def reset_slots(
    tracker: Tracker,
    flow: str,
    *,
    output: str = "dict",
) -> Union[Dict[Text, Any], List[SlotSet]]:
    if flow not in ["status_check", "new_grievance", "otp_submission"]:
        logger.error("reset_slots - flow: %s is not valid", flow)
        raise ValueError(f"reset_slots - flow: {flow} is not valid")

    dic_flow_prefix = {
        "status_check": {"prefix": ["status_check"], "avoid_slots": []},
        "new_grievance": {
            "prefix": ["grievance"],
            "avoid_slots": ["grievance_id", "complainant_id"],
        },
        "otp_submission": {"prefix": ["otp"], "avoid_slots": []},
    }
    prefix = dic_flow_prefix["otp_submission"]["prefix"]
    avoid_slots = dic_flow_prefix["otp_submission"]["avoid_slots"]
    if flow != "otp_submission":
        prefix = dic_flow_prefix[flow]["prefix"] + prefix
        avoid_slots = dic_flow_prefix[flow]["avoid_slots"] + avoid_slots

    slots_to_reset = [
        slot
        for slot in tracker.slots
        if any(p in slot for p in prefix) and slot not in avoid_slots
    ]
    logger.info("reset_slots - flow=%s slots_to_reset=%s", flow, slots_to_reset)

    if output == "dict":
        return {slot: None for slot in slots_to_reset}
    if output == "slot_list":
        return [SlotSet(slot, None) for slot in slots_to_reset]
    raise ValueError(f"reset_slots - unknown output: {output}")
