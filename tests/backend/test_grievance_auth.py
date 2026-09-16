"""
T3-06 step 3 — authn on GET /api/grievance/{id} and POST /{id}/status.

These two were the least-protected path to grievance data in the system: no authn,
no authz, no audit, no contract — while ticketing's supposedly "violating" direct
SQL read had a Keycloak JWT and a jurisdiction gate. The PATCHes 30 lines away were
already authenticated, so this was 2 of 5 endpoints, not a missing convention.

POST /status is the more serious of the two: unauthenticated it mutates grievance
state and fires SMS + email to the complainant, so an anonymous caller could drive
a complainant's notification stream.

Every test pins the key into the environment rather than relying on ambient config.
env.local ships TICKETING_SECRET_KEY empty with APP_ENV=dev AUTH_MODE=bypass, so an
un-pinned test would take the dev-bypass branch and assert nothing about auth.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.api.fastapi_app import app

KEY = "t3-06-test-key"
AUTH = {"x-api-key": KEY}


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def keyed():
    """A configured key — makes the check live rather than taking the dev bypass."""
    with patch.dict("os.environ", {"TICKETING_SECRET_KEY": KEY, "MESSAGING_API_KEY": ""}):
        yield


# ── GET /api/grievance/{id} ───────────────────────────────────────────────────


def test_get_grievance_without_key_is_401(client, keyed):
    """
    The check this ticket exists for.

    A real grievance is mocked in on purpose: without it the pre-fix response is a
    404 (id not found), which only shows the request was served. With it, the
    pre-fix response is 200 carrying grievance_description — the actual disclosure.
    Verified red: this returns 200 with the record on today's code.
    """
    with patch(
        "backend.api.routers.grievance.grievance_manager.get_grievance_by_id",
        return_value={"grievance_id": "B-GR-REAL", "grievance_description": "secret narrative"},
    ), patch(
        "backend.api.routers.grievance.grievance_manager.get_grievance_status_history",
        return_value=[],
    ), patch(
        "backend.api.routers.grievance.grievance_manager.get_grievance_files",
        return_value=[],
    ), patch(
        "backend.api.routers.grievance.grievance_manager.get_grievance_status",
        return_value=None,
    ):
        r = client.get("/api/grievance/B-GR-REAL")

    assert r.status_code == 401
    assert "secret narrative" not in r.text


def test_get_grievance_with_key_is_not_401(client, keyed):
    """A valid key still reaches the handler — 404 here means auth passed."""
    with patch(
        "backend.api.routers.grievance.grievance_manager.get_grievance_by_id",
        return_value=None,
    ):
        r = client.get("/api/grievance/missing-id", headers=AUTH)
    assert r.status_code == 404


def test_get_grievance_with_wrong_key_is_401(client, keyed):
    r = client.get("/api/grievance/any-id", headers={"x-api-key": "wrong"})
    assert r.status_code == 401


def test_get_grievance_200_with_key(client, keyed):
    """Full success path: a valid key returns the record."""
    with patch(
        "backend.api.routers.grievance.grievance_manager.get_grievance_by_id",
        return_value={"grievance_id": "B-GR-OK", "grievance_summary": "s"},
    ), patch(
        "backend.api.routers.grievance.grievance_manager.get_grievance_status_history",
        return_value=[],
    ), patch(
        "backend.api.routers.grievance.grievance_manager.get_grievance_files",
        return_value=[],
    ), patch(
        "backend.api.routers.grievance.grievance_manager.get_grievance_status",
        return_value=None,
    ):
        r = client.get("/api/grievance/B-GR-OK", headers=AUTH)

    assert r.status_code == 200
    assert r.json()["data"]["grievance"]["grievance_id"] == "B-GR-OK"


def test_get_grievance_messaging_key_is_accepted(client):
    """MESSAGING_API_KEY is the documented alternate credential."""
    with patch.dict(
        "os.environ", {"TICKETING_SECRET_KEY": "", "MESSAGING_API_KEY": "msg-key"}
    ):
        with patch(
            "backend.api.routers.grievance.grievance_manager.get_grievance_by_id",
            return_value=None,
        ):
            r = client.get("/api/grievance/missing", headers={"x-api-key": "msg-key"})
    assert r.status_code == 404


# ── POST /api/grievance/{id}/status ───────────────────────────────────────────


def test_post_status_without_key_is_401(client, keyed):
    """Unauthenticated, this mutates state and fires SMS + email to the complainant."""
    r = client.post("/api/grievance/any-id/status", json={"status_code": "RESOLVED"})
    assert r.status_code == 401


def test_post_status_without_key_does_not_notify_the_complainant(client, keyed):
    """
    The 401 must land before any side effect. A rejected request that still sent
    an SMS would defeat the point of authenticating this endpoint.
    """
    with patch(
        "backend.api.routers.grievance._send_status_update_notifications"
    ) as notify, patch(
        "backend.api.routers.grievance.grievance_manager.update_grievance_status"
    ) as update:
        r = client.post("/api/grievance/any-id/status", json={"status_code": "RESOLVED"})

    assert r.status_code == 401
    notify.assert_not_called()
    update.assert_not_called()


def test_post_status_with_key_is_not_401(client, keyed):
    with patch(
        "backend.api.routers.grievance.grievance_manager.get_grievance_by_id",
        return_value=None,
    ):
        r = client.post(
            "/api/grievance/missing-id/status",
            json={"status_code": "RESOLVED"},
            headers=AUTH,
        )
    assert r.status_code == 404


def test_post_status_200_with_key(client, keyed):
    with patch(
        "backend.api.routers.grievance.grievance_manager.get_grievance_by_id",
        return_value={"grievance_id": "B-GR-OK"},
    ), patch(
        "backend.api.routers.grievance.grievance_manager.update_grievance_status",
        return_value=True,
    ), patch(
        "backend.api.routers.grievance._send_status_update_notifications"
    ):
        r = client.post(
            "/api/grievance/B-GR-OK/status",
            json={"status_code": "RESOLVED"},
            headers=AUTH,
        )
    assert r.status_code == 200
    assert r.json()["status"] == "SUCCESS"


def test_auth_rejects_before_body_validation(client, keyed):
    """
    An invalid body without a key must 401, not 422 — a 422 would confirm to an
    unauthenticated caller that the endpoint exists and how to shape a request.
    """
    r = client.post("/api/grievance/any-id/status", json={})
    assert r.status_code == 401


# ── the guards that must survive ──────────────────────────────────────────────


def test_dev_bypass_still_works(client):
    """AUTH_MODE=bypass keeps the local loop working — env.local ships no key."""
    with patch.dict(
        "os.environ",
        {
            "TICKETING_SECRET_KEY": "",
            "MESSAGING_API_KEY": "",
            "APP_ENV": "dev",
            "AUTH_MODE": "bypass",
        },
    ):
        with patch(
            "backend.api.routers.grievance.grievance_manager.get_grievance_by_id",
            return_value=None,
        ):
            r = client.get("/api/grievance/missing")
    assert r.status_code == 404


def test_unconfigured_key_fails_closed_in_production(client):
    """
    HR-01: no key configured and no dev bypass must 503, never silently allow.
    An empty key list must not read as "auth disabled".
    """
    with patch.dict(
        "os.environ",
        {
            "TICKETING_SECRET_KEY": "",
            "MESSAGING_API_KEY": "",
            "APP_ENV": "production",
            "AUTH_MODE": "keycloak",
        },
    ):
        r = client.get("/api/grievance/any-id")
    assert r.status_code == 503


def test_statuses_endpoint_stays_public(client, keyed):
    """
    GET /api/grievance/statuses is a static code list with no grievance data and is
    out of scope. Pinned so the fixed path is not captured as {grievance_id} and
    silently gains auth.
    """
    r = client.get("/api/grievance/statuses")
    assert r.status_code == 200
    assert r.json()["status"] == "SUCCESS"
