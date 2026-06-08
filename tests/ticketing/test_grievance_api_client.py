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
