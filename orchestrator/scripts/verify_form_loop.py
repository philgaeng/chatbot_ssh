#!/usr/bin/env python3
"""
Verify form loop: simulate form turn with /submit_details.
Task 3.4: slot_updates and messages match expected.

Run from project root with Rasa env activated:
  python orchestrator/scripts/verify_form_loop.py
"""

import asyncio
import sys
import yaml
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator.form_loop import run_form_turn
from rasa_chatbot.actions.forms.form_grievance import ValidateFormGrievance


def load_domain() -> dict:
    """Load Rasa domain from YAML."""
    path = PROJECT_ROOT / "rasa_chatbot" / "domain.yml"
    with open(path) as f:
        return yaml.safe_load(f) or {}


async def verify_submit_details():
    """Simulate form turn with /submit_details; assert slot_updates and completed."""
    domain = load_domain()

    # Session after action_start_grievance_process + user entered some text
    session = {
        "user_id": "test_user",
        "state": "form_grievance",
        "active_loop": "form_grievance",
        "requested_slot": "grievance_new_detail",
        "slots": {
            "language_code": "en",
            "complainant_province": "Koshi",
            "complainant_district": "Jhapa",
            "story_main": "new_grievance",
            "grievance_id": "G-TEST-001",
            "complainant_id": "C-TEST-001",
            "grievance_sensitive_issue": False,
            "grievance_description": "My complaint is about delayed services",
            "grievance_new_detail": None,
            "grievance_description_status": "show_options",
        },
    }

    # user_input: Dict with text and intent (form_loop expects this)
    user_input = {
        "text": "/submit_details",
        "intent": {"name": "submit_details"},
    }

    form = ValidateFormGrievance()

    # Mock db_manager.create_complainant_and_grievance (called on submit_details)
    with patch.object(
        form.db_manager,
        "create_complainant_and_grievance",
        new_callable=AsyncMock,
    ) as mock_create:
        mock_create.return_value = None

        messages, slot_updates, completed = await run_form_turn(
            form=form,
            session=session,
            user_input=user_input,
            domain=domain,
        )

    # Expected: completed=True, grievance_new_detail="completed"
    assert completed, f"Expected completed=True, got completed={completed}"
    assert slot_updates.get("grievance_new_detail") == "completed", (
        f"Expected grievance_new_detail='completed', got {slot_updates.get('grievance_new_detail')}"
    )
    assert slot_updates.get("requested_slot") is None, (
        f"Expected requested_slot=None on completion, got {slot_updates.get('requested_slot')}"
    )

    print("OK: /submit_details -> completed=True, grievance_new_detail='completed'")
    print(f"  slot_updates: {slot_updates}")
    print(f"  messages: {messages}")


if __name__ == "__main__":
    asyncio.run(verify_submit_details())
