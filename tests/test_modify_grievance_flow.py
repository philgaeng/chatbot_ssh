"""
Modify grievance flow tests (Agent 11 / Spec 13).

Uses run_flow_turn with a prebuilt session; does not require the full
orchestrator app (no socketio). These tests define expected behaviour and
will pass once modify_grievance states/transitions are implemented.
"""

import asyncio
from pathlib import Path

import pytest
import yaml

# Project root and path setup (tests/ -> repo root)
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(_PROJECT_ROOT))

from backend.orchestrator.paths import DOMAIN_YAML_PATH
from backend.orchestrator.session_store import create_session
from backend.orchestrator.state_machine import run_flow_turn


def _load_domain() -> dict:
    path = DOMAIN_YAML_PATH
    if not path.exists():
        return {"slots": {}}
    with path.open() as f:
        return yaml.safe_load(f) or {}


@pytest.fixture(scope="module")
def domain():
    return _load_domain()


def _session_at_status_check_details(user_id: str) -> dict:
    """Session after user has seen grievance details (Request follow up | Modify | Skip)."""
    session = create_session(user_id)
    session["state"] = "status_check_form"
    session["active_loop"] = None
    session["requested_slot"] = None
    session["slots"]["story_main"] = "status_check"
    session["slots"]["status_check_grievance_id_selected"] = "GR-TEST-1234-A"
    return session


@pytest.mark.xfail(reason="Implement transition to modify_grievance_menu in state_machine (Agent 11)")
def test_modify_grievance_from_status_check_goes_to_menu(domain: dict):
    """From status-check details, /status_check_modify_grievance → modify_grievance_menu with three options + Cancel."""
    user_id = "modify-test-menu-1"
    session = _session_at_status_check_details(user_id)
    session["user_id"] = user_id

    messages, next_state, _ = asyncio.run(
        run_flow_turn(session, "", "/status_check_modify_grievance", domain)
    )

    assert next_state == "modify_grievance_menu", (
        f"Expected modify_grievance_menu, got {next_state}. "
        "Implement transition from status_check_form to modify_grievance_menu when intent is status_check_modify_grievance."
    )
    assert isinstance(messages, list)
    has_buttons = any("buttons" in m for m in messages)
    assert has_buttons, "Modify menu should include buttons (Add pictures, Add more info, Add missing info, Cancel)"


@pytest.mark.xfail(reason="Implement modify_grievance_menu state and cancel transition (Agent 11)")
def test_modify_grievance_cancel_returns_to_status_check_form(domain: dict):
    """From modify_grievance_menu, Cancel → back to status_check_form (same grievance)."""
    user_id = "modify-test-cancel-1"
    session = create_session(user_id)
    session["user_id"] = user_id
    session["state"] = "modify_grievance_menu"
    session["active_loop"] = None
    session["requested_slot"] = None
    session["slots"]["story_main"] = "status_check"
    session["slots"]["status_check_grievance_id_selected"] = "GR-TEST-5678-A"

    messages, next_state, _ = asyncio.run(
        run_flow_turn(session, "", "/modify_grievance_cancel", domain)
    )

    assert next_state == "status_check_form", (
        f"Expected status_check_form after Cancel, got {next_state}. "
        "Implement modify_grievance_cancel transition to status_check_form."
    )
    assert session["slots"].get("status_check_grievance_id_selected") == "GR-TEST-5678-A"
