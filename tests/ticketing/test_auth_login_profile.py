"""Login profile repair must not clear Keycloak onboarding required actions."""
from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

# auth_login imports python-jose at module load time
if "jose" not in sys.modules:
    _jose = ModuleType("jose")
    _jwt = ModuleType("jose.jwt")
    _jwt.encode = MagicMock()
    _jwt.decode = MagicMock()
    _jose.JWTError = Exception
    _jose.jwt = _jwt
    sys.modules["jose"] = _jose
    sys.modules["jose.jwt"] = _jwt

from ticketing.services.auth_login import (
    AuthLoginError,
    _ensure_keycloak_profile_ready,
    login_with_password,
)


def test_ensure_keycloak_profile_ready_preserves_onboarding_actions_by_default():
    admin = MagicMock()
    user = {
        "id": "kc-1",
        "email": "officer@example.com",
        "firstName": "Officer",
        "lastName": "User",
        "requiredActions": ["UPDATE_PASSWORD"],
        "attributes": {"phone_number": ["9800000000"]},
    }

    _ensure_keycloak_profile_ready(admin, user, "officer@example.com")

    admin.update_user.assert_not_called()


def test_ensure_keycloak_profile_ready_fills_missing_fields_without_clearing_actions():
    admin = MagicMock()
    user = {
        "id": "kc-1",
        "email": "",
        "firstName": "",
        "lastName": "",
        "requiredActions": ["UPDATE_PASSWORD"],
        "attributes": {},
    }

    _ensure_keycloak_profile_ready(admin, user, "officer@example.com")

    admin.update_user.assert_called_once()
    payload = admin.update_user.call_args[0][1]
    assert "requiredActions" not in payload
    assert payload["firstName"] == "Officer"
    assert payload["attributes"]["phone_number"] == ["9800000000"]


def test_login_rejects_pending_onboarding_instead_of_clearing_actions():
    user = {
        "id": "kc-1",
        "email": "officer@example.com",
        "requiredActions": ["UPDATE_PASSWORD"],
    }
    token_resp = MagicMock()
    token_resp.is_success = False
    token_resp.status_code = 400
    token_resp.json.return_value = {
        "error": "invalid_grant",
        "error_description": "Account is not fully set up",
    }

    with patch(
        "ticketing.services.auth_login.keycloak_configured",
        return_value=True,
    ), patch(
        "ticketing.services.auth_login.get_settings",
    ) as gs, patch(
        "ticketing.services.auth_login._api_client_secret",
        return_value="secret",
    ), patch(
        "ticketing.services.auth_login._password_token_request",
        return_value=token_resp,
    ), patch(
        "ticketing.services.auth_login._find_keycloak_user",
        return_value=user,
    ), patch(
        "ticketing.services.auth_login._ensure_keycloak_profile_ready",
    ) as repair:
        gs.return_value.keycloak_issuer = "http://keycloak/realms/grm"
        gs.return_value.keycloak_client_id = "ticketing-api"
        with pytest.raises(AuthLoginError) as exc:
            login_with_password("officer@example.com", "GrmDemo2026!")

    assert exc.value.code == "account_setup_required"
    repair.assert_not_called()
