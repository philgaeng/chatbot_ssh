"""Shared helpers for orchestrator end-to-end flow tests."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Set

from fastapi.testclient import TestClient

from backend.actions.utils.mapping_buttons import (
    BUTTON_LOCATION_MANUAL,
    BUTTON_LOCATION_USE_MAP,
    BUTTON_LOCATION_USE_PHONE,
)

LOCATION_METHOD_PAYLOADS = frozenset(
    {
        BUTTON_LOCATION_USE_PHONE,
        BUTTON_LOCATION_USE_MAP,
        BUTTON_LOCATION_MANUAL,
    }
)

SKIP_PAYLOADS = frozenset({"/skip", "/affirm_skip"})


def post_turn(
    client: TestClient,
    user_id: str,
    *,
    text: str = "",
    payload: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {"user_id": user_id, "text": text}
    if payload is not None:
        body["payload"] = payload
    if metadata:
        body["metadata"] = metadata
    response = client.post("/message", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def all_button_payloads(response_body: Dict[str, Any]) -> List[str]:
    payloads: List[str] = []
    for message in response_body.get("messages") or []:
        for button in message.get("buttons") or []:
            payload = button.get("payload")
            if payload:
                payloads.append(payload)
    return payloads


def all_json_events(
    response_body: Dict[str, Any], event_type: str
) -> List[Dict[str, Any]]:
    found: List[Dict[str, Any]] = []
    for message in response_body.get("messages") or []:
        data = (message.get("json_message") or {}).get("data") or {}
        if data.get("event_type") == event_type:
            found.append(data)
        custom = message.get("custom") or {}
        if custom.get("event_type") == event_type:
            found.append(custom)
    return found


def has_json_event(response_body: Dict[str, Any], event_type: str) -> bool:
    return bool(all_json_events(response_body, event_type))


def assert_location_method_three_options(response_body: Dict[str, Any]) -> None:
    """Location method step must offer phone, map, and manual entry."""
    payloads = set(all_button_payloads(response_body))
    missing = LOCATION_METHOD_PAYLOADS - payloads
    assert not missing, (
        f"location_method must offer phone, map, and manual; missing {missing}; "
        f"got {sorted(payloads)}"
    )


def intro_english(client: TestClient, user_id: str) -> Dict[str, Any]:
    post_turn(client, user_id, text="")
    return post_turn(client, user_id, payload="/set_english")


def accept_location_consent(client: TestClient, user_id: str) -> Dict[str, Any]:
    return post_turn(client, user_id, payload="/affirm")


def choose_location_manual(client: TestClient, user_id: str) -> Dict[str, Any]:
    return post_turn(client, user_id, payload=BUTTON_LOCATION_MANUAL)


def choose_location_map(client: TestClient, user_id: str) -> Dict[str, Any]:
    return post_turn(client, user_id, payload=BUTTON_LOCATION_USE_MAP)


def submit_map_pin(
    client: TestClient, user_id: str, *, lat: float = 26.64, lng: float = 87.99
) -> Dict[str, Any]:
    return post_turn(
        client,
        user_id,
        text="",
        metadata={"map_pin": {"lat": lat, "lng": lng}},
    )


def _last_prompt_text(response_body: Dict[str, Any]) -> str:
    for message in reversed(response_body.get("messages") or []):
        text = (message.get("text") or "").strip()
        if text:
            return text.lower()
    return ""


def complete_contact_for_test(
    client: TestClient, user_id: str, body: Dict[str, Any], *, max_rounds: int = 35
) -> Dict[str, Any]:
    """
    Fill or skip contact/location fields, then decline contact consent (skips OTP).
    """
    current = body
    seen: Set[str] = set()
    for _ in range(max_rounds):
        state = current.get("next_state")
        if state not in ("contact_form", "otp_form"):
            return current

        fingerprint = f"{state}|{_last_prompt_text(current)}"
        if fingerprint in seen:
            break
        seen.add(fingerprint)

        payloads = all_button_payloads(current)
        prompt = _last_prompt_text(current)

        if state == "otp_form":
            if "/deny" in payloads:
                current = post_turn(client, user_id, payload="/deny")
                continue
            if "/skip" in payloads:
                current = post_turn(client, user_id, payload="/skip")
                continue
            current = post_turn(client, user_id, payload="/skip")
            continue

        if "would you like to provide your contact" in prompt or "contact information" in prompt:
            if "/deny" in payloads:
                current = post_turn(client, user_id, payload="/deny")
                continue

        if "share your location" in prompt or "location details" in prompt:
            if "/affirm" in payloads:
                current = post_turn(client, user_id, payload="/affirm")
                continue
            if "/deny" in payloads:
                current = post_turn(client, user_id, payload="/deny")
                continue

        if "province" in prompt:
            current = post_turn(client, user_id, text="Koshi")
            continue
        if "district" in prompt:
            current = post_turn(client, user_id, text="Jhapa")
            continue
        if "municipality" in prompt and "correct" in prompt:
            if "/affirm" in payloads:
                current = post_turn(client, user_id, payload="/affirm")
                continue
            if "/deny" in payloads:
                current = post_turn(client, user_id, payload="/deny")
                continue
        if "municipality" in prompt:
            current = post_turn(client, user_id, text="Birtamod")
            continue
        if "village" in prompt:
            current = post_turn(client, user_id, payload="/skip")
            continue
        if "ward" in prompt:
            current = post_turn(client, user_id, payload="/skip")
            continue
        if "location details" in prompt or "address" in prompt and "correct" in prompt:
            if "/slot_confirmed" in payloads:
                current = post_turn(client, user_id, payload="/slot_confirmed")
                continue
            if "/affirm" in payloads:
                current = post_turn(client, user_id, payload="/affirm")
                continue
        if "address" in prompt:
            if "/skip" in payloads:
                current = post_turn(client, user_id, payload="/skip")
                continue
            if "/affirm" in payloads or "/slot_confirmed" in payloads:
                current = post_turn(client, user_id, payload="/slot_confirmed")
                continue
            current = post_turn(client, user_id, text="Main road")
            continue

        if "/slot_confirmed" in payloads:
            current = post_turn(client, user_id, payload="/slot_confirmed")
            continue
        if "/skip" in payloads:
            current = post_turn(client, user_id, payload="/skip")
            continue
        if "/deny" in payloads:
            current = post_turn(client, user_id, payload="/deny")
            continue
        break
    return current


# Backwards-compatible alias
def skip_contact_and_decline_consent(
    client: TestClient, user_id: str, body: Dict[str, Any], *, max_rounds: int = 40
) -> Dict[str, Any]:
    return complete_contact_for_test(client, user_id, body, max_rounds=max_rounds)


def advance_seah_anonymous_victim_flow(
    client: TestClient, user_id: str, body: Dict[str, Any], *, max_rounds: int = 50
) -> Dict[str, Any]:
    """Walk dedicated SEAH victim/survivor anonymous intake toward submit."""
    current = body
    for _ in range(max_rounds):
        if has_json_event(current, "grievance_filed") or current.get("next_state") == "done":
            return current
        state = current.get("next_state")
        payloads = all_button_payloads(current)
        prompt = _last_prompt_text(current)

        if state in ("contact_form", "otp_form"):
            current = complete_contact_for_test(client, user_id, current)
            continue
        if state == "grievance_review":
            current = complete_grievance_review(client, user_id, current)
            continue
        if state == "location_consent" and "/affirm" in payloads:
            current = accept_location_consent(client, user_id)
            continue
        if state == "location_method":
            current = choose_location_manual(client, user_id)
            continue

        if "adb project" in prompt or "perpetrator" in prompt:
            if "/no" in payloads:
                current = post_turn(client, user_id, payload="/no")
                continue
            if "/yes" in payloads:
                current = post_turn(client, user_id, payload="/yes")
                continue
        if "/cannot_specify" in payloads and "project" in prompt:
            current = post_turn(client, user_id, payload="/cannot_specify")
            continue
        if "/not_adb_project" in payloads and "adb project" in prompt:
            current = post_turn(client, user_id, payload="/not_adb_project")
            continue
        if "/cannot_specify" in payloads:
            current = post_turn(client, user_id, payload="/cannot_specify")
            continue
        if "/submit_details" in payloads:
            current = post_turn(client, user_id, payload="/submit_details")
            continue
        if "/selection_done" in payloads:
            current = post_turn(client, user_id, payload="/selection_done")
            continue
        if "/skip" in payloads:
            current = post_turn(client, user_id, payload="/skip")
            continue
        if "/affirm" in payloads:
            current = post_turn(client, user_id, payload="/affirm")
            continue
        if "province" in prompt:
            current = post_turn(client, user_id, text="Koshi")
            continue
        if "district" in prompt:
            current = post_turn(client, user_id, text="Jhapa")
            continue
        if "municipality" in prompt:
            current = post_turn(client, user_id, text="Birtamod")
            continue
        if "detail" in prompt or "describe" in prompt or "incident" in prompt:
            current = post_turn(
                client,
                user_id,
                text="Ongoing harassment by contractor staff near site camp.",
            )
            continue
        break
    return current


def complete_grievance_review(
    client: TestClient, user_id: str, body: Dict[str, Any], *, max_rounds: int = 30
) -> Dict[str, Any]:
    current = body
    for _ in range(max_rounds):
        if current.get("next_state") == "done":
            return current
        if current.get("next_state") != "grievance_review":
            return current
        payloads = all_button_payloads(current)
        if "/slot_confirmed" in payloads:
            current = post_turn(client, user_id, payload="/slot_confirmed")
        elif "/affirm" in payloads:
            current = post_turn(client, user_id, payload="/affirm")
        elif "/deny" in payloads:
            current = post_turn(client, user_id, payload="/deny")
        elif "/selection_done" in payloads:
            current = post_turn(client, user_id, payload="/selection_done")
        else:
            current = post_turn(client, user_id, payload="/slot_confirmed")
    return current


def drive_until_filed_or_done(
    client: TestClient,
    user_id: str,
    body: Dict[str, Any],
    *,
    max_rounds: int = 60,
) -> Dict[str, Any]:
    current = body
    for _ in range(max_rounds):
        if has_json_event(current, "grievance_filed"):
            return current
        if current.get("next_state") == "done":
            return current
        state = current.get("next_state")
        if state == "grievance_review":
            current = complete_grievance_review(client, user_id, current)
            continue
        if state in ("contact_form", "otp_form"):
            current = complete_contact_for_test(client, user_id, current)
            continue
        payloads = all_button_payloads(current)
        if state == "location_consent" and "/affirm" in payloads:
            current = accept_location_consent(client, user_id)
            continue
        if state == "location_method":
            assert_location_method_three_options(current)
            current = choose_location_manual(client, user_id)
            continue
        if state in (
            "form_seah_1",
            "form_seah_2",
            "form_seah_focal_point_1",
            "form_seah_focal_point_2",
        ):
            current = advance_seah_anonymous_victim_flow(client, user_id, current, max_rounds=8)
            continue
        if state == "map_location" and "/location_open_map" in payloads:
            current = post_turn(client, user_id, payload="/location_open_map")
            continue
        if "/submit_details" in payloads:
            current = post_turn(client, user_id, payload="/submit_details")
            continue
        if "/skip" in payloads:
            current = post_turn(client, user_id, payload="/skip")
            continue
        if "/affirm" in payloads:
            current = post_turn(client, user_id, payload="/affirm")
            continue
        break
    return current
