"""Centralized form-to-form routing (story_main → form → route → step)."""

from __future__ import annotations

import logging
from typing import Text

from rasa_sdk import Tracker

logger = logging.getLogger(__name__)


def get_next_action_for_form(tracker: Tracker, *, skip_value: str) -> str:
    active_loop = tracker.active_loop
    form_name = active_loop.get("name") if active_loop else None

    if not form_name:
        latest_action_name = tracker.latest_action_name
        if latest_action_name and latest_action_name.startswith("form_"):
            form_name = latest_action_name
            logger.debug("get_next_action_for_form - Using completed form: %s", form_name)

    story_main = tracker.get_slot("story_main")
    story_route = tracker.get_slot("story_route")
    story_step = tracker.get_slot("story_step")
    grievance_sensitive_issue = tracker.get_slot("grievance_sensitive_issue")
    seah_victim_survivor_role = tracker.get_slot("seah_victim_survivor_role")

    logger.debug(
        "get_next_action_for_form - story: %s, form: %s, route: %s, step: %s",
        story_main,
        form_name,
        story_route,
        story_step,
    )

    if story_main in ("new_grievance", "seah_intake"):
        if form_name == "form_grievance" and grievance_sensitive_issue is True:
            return "form_seah_1"
        if form_name == "form_seah_1":
            if grievance_sensitive_issue is False:
                return "form_grievance" if story_main == "new_grievance" else "action_outro_sensitive_issues"
            return "form_otp"
        if form_name == "form_otp" and (
            grievance_sensitive_issue is True or story_main == "seah_intake"
        ):
            return "form_contact"
        if form_name == "form_contact" and (
            grievance_sensitive_issue is True or story_main == "seah_intake"
        ):
            if seah_victim_survivor_role == "focal_point":
                return "form_seah_focal_point_1"
            return "form_seah_2"
        if form_name in ("form_seah_2", "form_seah_focal_point_1", "form_seah_focal_point_2"):
            return "action_submit_grievance"

    dic_status_check_next_action = {
        skip_value: "action_skip_status_check_outro",
        "status_check_modify": "form_status_check_modify",
        "status_check_follow_up": "action_status_check_follow_up",
    }
    routing_map = {
        "new_grievance": {
            "form_grievance": "form_contact",
            "form_contact": "form_otp",
            "form_otp": "action_submit_grievance",
            "None": "action_next_action",
        },
        "seah_intake": {
            "form_seah_1": "form_otp",
            "form_otp": "form_contact",
            "form_contact": "form_seah_2",
            "form_seah_2": "action_submit_grievance",
            "form_seah_focal_point_1": "form_seah_focal_point_2",
            "form_seah_focal_point_2": "action_submit_grievance",
            "None": "action_next_action",
        },
        "status_check": {
            "form_status_check_1": {
                "route_status_check_grievance_id": "form_story_step",
                "route_status_check_phone": "form_otp",
                skip_value: "form_status_check_skip",
            },
            "form_status_check_2": "form_story_step",
            "form_otp": {
                "route_status_check_phone": "form_status_check_2",
                skip_value: "form_status_check_skip",
                "route_status_check_grievance_id": dic_status_check_next_action,
            },
            "form_story_step": {
                skip_value: "form_status_check_skip",
                "route_status_check_grievance_id": "form_otp",
                "route_status_check_phone": dic_status_check_next_action,
            },
            "form_status_check_skip": "action_skip_status_check_outro",
            "form_story_step": {
                "route_status_check_grievance_id": {
                    "status_check_request_follow_up": "action_status_check_request_follow_up",
                    "status_check_modify": "form_status_check_modify",
                },
                "route_status_check_phone": {
                    "status_check_request_follow_up": "action_status_check_request_follow_up",
                    "status_check_modify": "form_status_check_modify",
                },
            },
        },
    }

    if story_main not in routing_map:
        error_msg = (
            f"No routing found for story_main: '{story_main}'. "
            f"Available stories: {list(routing_map.keys())}"
        )
        logger.error(error_msg)
        raise ValueError(error_msg)

    next_action = routing_map[story_main]

    if isinstance(next_action, dict):
        if form_name not in next_action:
            error_msg = (
                f"No routing found for form: '{form_name}' in story: '{story_main}'. "
                f"Available forms: {list(next_action.keys())}"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)
        next_action = next_action[form_name]

    if isinstance(next_action, dict):
        if story_route and story_route in next_action:
            next_action = next_action[story_route]
        elif "default" in next_action:
            logger.debug("Using default route for story_route: %s", story_route)
            next_action = next_action["default"]
        else:
            error_msg = (
                f"No routing found for story_route: '{story_route}' in form: "
                f"'{form_name}', story: '{story_main}'. "
                f"Available routes: {list(next_action.keys())}"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

    if isinstance(next_action, dict):
        if story_step and story_step in next_action:
            next_action = next_action[story_step]
        elif "default" in next_action:
            logger.debug("Using default route for story_step: %s", story_step)
            next_action = next_action["default"]
        else:
            error_msg = (
                f"No routing found for story_step: '{story_step}' in route: "
                f"'{story_route}', form: '{form_name}', story: '{story_main}'. "
                f"Available steps: {list(next_action.keys())}"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

    if not next_action or not isinstance(next_action, str):
        error_msg = (
            f"Invalid routing result: {next_action} for form: '{form_name}', "
            f"story: '{story_main}', route: '{story_route}', step: '{story_step}'"
        )
        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.debug("get_next_action_for_form - resolved next_action: %s", next_action)
    return next_action
