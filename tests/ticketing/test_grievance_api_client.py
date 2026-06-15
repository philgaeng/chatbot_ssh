"""Ticketing → backend grievance API client (auth headers)."""

from unittest.mock import MagicMock, patch

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
