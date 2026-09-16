"""Ticketing → backend grievance API client (auth headers)."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from ticketing.clients import grievance_api
from ticketing.clients.backend_auth import service_integration_api_key


def test_service_integration_api_key_prefers_ticketing_secret():
    settings = MagicMock()
    settings.ticketing_secret_key = "ticketing-secret"
    settings.messaging_api_key = "messaging-key"

    with patch("ticketing.clients.backend_auth.get_settings", return_value=settings):
        assert service_integration_api_key() == "ticketing-secret"


def test_patch_grievance_classification_uses_ticketing_secret_key():
    settings = MagicMock()
    settings.backend_grievance_base_url = "http://backend:5001"
    settings.ticketing_secret_key = "ticketing-secret"
    settings.messaging_api_key = "messaging-key"

    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {"ok": True}

    client = MagicMock()
    client.patch.return_value = response
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)

    with patch("ticketing.clients.backend_auth.get_settings", return_value=settings), patch.object(
        grievance_api, "_client", return_value=client
    ):
        grievance_api.patch_grievance_classification(
            "B-GR-TEST",
            grievance_classification_status="officer_confirmed",
            grievance_summary="Summary",
            grievance_categories=["Environmental - Air Pollution"],
        )

    client.patch.assert_called_once()
    _, kwargs = client.patch.call_args
    assert kwargs["headers"]["x-api-key"] == "ticketing-secret"


def test_update_grievance_status_uses_backend_body_keys():
    """POST body must match UpdateStatusBody (status_code, notes) — not status/note."""
    settings = MagicMock()
    settings.backend_grievance_base_url = "http://backend:5001"

    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {"status": "SUCCESS"}

    client = MagicMock()
    client.post.return_value = response
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)

    with patch("ticketing.clients.grievance_api.get_settings", return_value=settings), patch.object(
        grievance_api, "_client", return_value=client
    ):
        grievance_api.update_grievance_status(
            "B-GR-20260614-KOJH-AAB8",
            "RESOLVED",
            note="Officer resolution notes",
            created_by="officer@grm.local",
        )

    client.post.assert_called_once_with(
        "/api/grievance/B-GR-20260614-KOJH-AAB8/status",
        json={
            "status_code": "RESOLVED",
            "notes": "Officer resolution notes",
            "created_by": "officer@grm.local",
        },
    )


# ── T3-06: every call through this module must authenticate ───────────────────
#
# The tests above stub _client() out entirely, so they assert the request body but
# say nothing about what reaches the wire. That is how the gap survived: the GET and
# POST /status sent no x-api-key at all while the two PATCHes did, and no test could
# see it. These drive the real _client() through a MockTransport and assert on the
# outbound request, so the key is checked where it actually matters.


@pytest.fixture
def wire(monkeypatch):
    """Capture the real outbound request built by _client()."""
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["headers"] = request.headers
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"status": "SUCCESS", "data": {}})

    real_client = httpx.Client

    def fake_client(**kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(**kwargs)

    monkeypatch.setattr(httpx, "Client", fake_client)
    return seen


def _settings():
    settings = MagicMock()
    settings.backend_grievance_base_url = "http://backend:5001"
    settings.ticketing_secret_key = "ticketing-secret"
    settings.messaging_api_key = ""
    return settings


def test_get_grievance_detail_sends_api_key(wire):
    """Verified red pre-fix: the GET sent no key, so this endpoint 401s once authn lands."""
    with patch("ticketing.clients.grievance_api.get_settings", return_value=_settings()), patch(
        "ticketing.clients.backend_auth.get_settings", return_value=_settings()
    ):
        grievance_api.get_grievance_detail("B-GR-TEST")

    assert wire["headers"]["x-api-key"] == "ticketing-secret"


def test_update_grievance_status_sends_api_key(wire):
    """
    The most serious of the two: unauthenticated, this endpoint mutates grievance
    state and fires SMS + email to the complainant.
    """
    with patch("ticketing.clients.grievance_api.get_settings", return_value=_settings()), patch(
        "ticketing.clients.backend_auth.get_settings", return_value=_settings()
    ):
        grievance_api.update_grievance_status("B-GR-TEST", "RESOLVED", note="done")

    assert wire["headers"]["x-api-key"] == "ticketing-secret"


def test_get_grievance_statuses_sends_api_key(wire):
    with patch("ticketing.clients.grievance_api.get_settings", return_value=_settings()), patch(
        "ticketing.clients.backend_auth.get_settings", return_value=_settings()
    ):
        grievance_api.get_grievance_statuses()

    assert wire["headers"]["x-api-key"] == "ticketing-secret"


def test_no_api_key_configured_omits_the_header(wire):
    """
    An unset key must omit the header, not send an empty one. Both 401 at the
    backend, but an empty x-api-key misreports the caller as presenting a
    credential — it would log as 'unrecognized-key' rather than 'anonymous'.
    """
    settings = _settings()
    settings.ticketing_secret_key = ""
    settings.messaging_api_key = ""

    with patch("ticketing.clients.grievance_api.get_settings", return_value=settings), patch(
        "ticketing.clients.backend_auth.get_settings", return_value=settings
    ):
        grievance_api.get_grievance_detail("B-GR-TEST")

    assert "x-api-key" not in wire["headers"]


def test_messaging_key_is_used_when_ticketing_secret_is_unset(wire):
    settings = _settings()
    settings.ticketing_secret_key = ""
    settings.messaging_api_key = "messaging-key"

    with patch("ticketing.clients.grievance_api.get_settings", return_value=settings), patch(
        "ticketing.clients.backend_auth.get_settings", return_value=settings
    ):
        grievance_api.get_grievance_detail("B-GR-TEST")

    assert wire["headers"]["x-api-key"] == "messaging-key"
