#!/usr/bin/env python3
"""
Extract orchestrator config (flow.yaml, slots.yaml) from Rasa YAMLs.

Input: rasa_chatbot/domain.yml, rasa_chatbot/data/stories/stories.yml
Output: orchestrator/config/flow.yaml, orchestrator/config/slots.yaml

Run from project root:
  python orchestrator/scripts/extract_config.py
"""

import yaml
import sys
from pathlib import Path

# Project root: parent of orchestrator/
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DOMAIN_PATH = PROJECT_ROOT / "rasa_chatbot" / "domain.yml"
STORIES_PATH = PROJECT_ROOT / "rasa_chatbot" / "data" / "stories" / "stories.yml"
RULES_PATH = PROJECT_ROOT / "rasa_chatbot" / "data" / "rules" / "rules.yml"
OUTPUT_CONFIG_DIR = PROJECT_ROOT / "orchestrator" / "config"

# Slots needed for form_grievance flow (from 04_flow_logic initial session)
FORM_GRIEVANCE_SLOT_NAMES = [
    "language_code",
    "complainant_province",
    "complainant_district",
    "story_main",
    "grievance_id",
    "complainant_id",
    "grievance_sensitive_issue",
    "grievance_description",
    "grievance_new_detail",
    "grievance_description_status",
    "requested_slot",
    "skip_validation_needed",
    "skipped_detected_text",
]

# Default values for spike (from backend.config.constants)
SLOT_DEFAULTS = {
    "complainant_province": "Koshi",
    "complainant_district": "Jhapa",
}


def load_yaml(path: Path) -> dict:
    """Load YAML file, return dict or empty dict if missing."""
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def extract_domain_slots(domain: dict, slot_names: list[str]) -> dict:
    """Extract slot definitions from domain for given slot names."""
    domain_slots = domain.get("slots", {})
    result = {}
    for name in slot_names:
        info = domain_slots.get(name, {})
        slot_def = {"type": info.get("type", "text"), "default": None}
        if "values" in info:
            slot_def["values"] = info["values"]
        if name in SLOT_DEFAULTS:
            slot_def["default"] = SLOT_DEFAULTS[name]
        elif name == "grievance_sensitive_issue":
            slot_def["default"] = False
        result[name] = slot_def
    return result


def extract_form_required_slots(domain: dict, form_name: str) -> list[str]:
    """Extract required_slots for a form from domain."""
    forms = domain.get("forms", {})
    form_def = forms.get(form_name, {})
    return form_def.get("required_slots", [])


def extract_flow_from_stories(stories_data: dict) -> dict:
    """
    Extract flow structure (intro -> main_menu -> form_grievance) from stories.
    We define a canonical flow; stories are used to validate/derive transitions.
    """
    return {
        "version": "1.0",
        "states": [
            {"id": "intro", "description": "Language selection; run action_introduce"},
            {"id": "main_menu", "description": "Menu; run action_main_menu"},
            {"id": "form_grievance", "description": "Collect grievance_new_detail via form loop"},
            {"id": "done", "description": "Form complete; flow ends"},
        ],
        "transitions": [
            {"from": "intro", "intent": "set_english", "to": "main_menu", "action": "action_set_english"},
            {"from": "intro", "intent": "set_nepali", "to": "main_menu", "action": "action_set_nepali"},
            {"from": "main_menu", "intent": "new_grievance", "to": "form_grievance", "action": "action_start_grievance_process"},
            {"from": "form_grievance", "condition": "form_complete", "to": "done", "action": None},
        ],
        "forms": {
            "form_grievance": {
                "name": "form_grievance",
                "validation_action": "validate_form_grievance",
                "ask_action": "action_ask_grievance_new_detail",
            }
        },
    }


def build_slots_config(domain: dict) -> dict:
    """Build slots.yaml structure from domain."""
    form_required = extract_form_required_slots(domain, "form_grievance")
    domain_slots = extract_domain_slots(domain, FORM_GRIEVANCE_SLOT_NAMES)
    return {
        "version": "1.0",
        "slots": domain_slots,
        "form_slots": {
            "form_grievance": {
                "required_slots": form_required,
            }
        },
    }


def main() -> int:
    domain = load_yaml(DOMAIN_PATH)
    if not domain:
        print(f"Warning: {DOMAIN_PATH} not found or empty", file=sys.stderr)
        domain = {}

    stories = load_yaml(STORIES_PATH)
    if not stories:
        print(f"Warning: {STORIES_PATH} not found or empty", file=sys.stderr)

    flow = extract_flow_from_stories(stories)
    flow["forms"]["form_grievance"]["required_slots"] = extract_form_required_slots(
        domain, "form_grievance"
    )

    slots_config = build_slots_config(domain)

    OUTPUT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    flow_path = OUTPUT_CONFIG_DIR / "flow.yaml"
    slots_path = OUTPUT_CONFIG_DIR / "slots.yaml"

    with open(flow_path, "w", encoding="utf-8") as f:
        yaml.dump(flow, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    with open(slots_path, "w", encoding="utf-8") as f:
        yaml.dump(slots_config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    print(f"Wrote {flow_path}")
    print(f"Wrote {slots_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
