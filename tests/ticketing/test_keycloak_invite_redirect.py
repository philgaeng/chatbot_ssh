# SPDX-License-Identifier: Apache-2.0
"""
An admin can send an officer's setup email from any host the officer UI is served on.

**Measured on staging 2026-09-15:** appointing an admin failed with
`Keycloak error: 400: b'{"errorMessage":"Invalid redirect uri."}'`. The invite asks Keycloak to send
the officer back to `KEYCLOAK_INVITE_REDIRECT_URI` (`https://nepal-gms-chatbot.facets-ai.com/login`),
and Keycloak refuses to send the email at all when that address is not in the `ticketing-ui` client's
`redirectUris` — which `keycloak_setup.py` hardcoded, naming only the old `grm-auth.` subdomain.

These pin: the host's own invite address is always allowed by the setup script; a refusal reads as
something an admin can act on, not as raw Keycloak bytes; and the preflight catches it before a send.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from ticketing.auth import keycloak_setup as ks

STAGING_INVITE = "https://nepal-gms-chatbot.facets-ai.com/login"
# `ticketing-ui` redirectUris as read back from staging's realm on 2026-09-15.
STAGING_REDIRECTS_BEFORE = [
    "https://grm-chatbot.dor.gov.np/*",
    "https://grm.facets-ai.com/*",
    "http://localhost:3002/*",
    "http://localhost:3001/*",
    "https://grm.stage.facets-ai.com/*",
    "https://grm-auth.nepal-gms-chatbot.facets-ai.com/*",
]
KEYCLOAK_REFUSAL = Exception('400: b\'{"errorMessage":"Invalid redirect uri."}\'')


def _settings(invite_uri: str) -> SimpleNamespace:
    return SimpleNamespace(keycloak_invite_redirect_uri=invite_uri)


def _ui_payload_written(invite_uri: str) -> dict:
    admin = MagicMock()
    admin.get_clients.return_value = [
        {"clientId": ks.CLIENT_UI, "id": "ui-uuid"},
        {"clientId": ks.CLIENT_API, "id": "api-uuid"},
    ]
    with patch.object(ks, "get_settings", return_value=_settings(invite_uri)):
        ks.setup_clients(admin)
    return next(c.args[1] for c in admin.update_client.call_args_list if c.args[0] == "ui-uuid")


def test_keycloak_matching_rule() -> None:
    assert ks.redirect_uri_allowed("https://a.example/login", ["https://a.example/*"])
    assert ks.redirect_uri_allowed("https://a.example/login", ["https://a.example/login"])
    assert not ks.redirect_uri_allowed("https://a.example/login", ["https://a.example/"])
    assert not ks.redirect_uri_allowed("https://b.a.example/login", ["https://a.example/*"])


def test_the_staging_redirect_was_refused_by_the_old_list() -> None:
    """The defect as measured — so the rule above is known to reproduce it."""
    assert not ks.redirect_uri_allowed(STAGING_INVITE, STAGING_REDIRECTS_BEFORE)


def test_setup_allows_the_staging_host() -> None:
    payload = _ui_payload_written("http://localhost:3002/login")
    assert ks.redirect_uri_allowed(STAGING_INVITE, payload["redirectUris"])
    assert STAGING_INVITE in payload["attributes"]["post.logout.redirect.uris"].split("##")


@pytest.mark.parametrize("invite_uri", ["https://officers.new-host.example/login", "http://10.0.0.5:3001/login"])
def test_setup_always_allows_this_hosts_own_invite_address(invite_uri: str) -> None:
    """⭐ The recurrence guard: a host not in `UI_ORIGINS` still sends invites after a setup run."""
    payload = _ui_payload_written(invite_uri)
    assert ks.redirect_uri_allowed(invite_uri, payload["redirectUris"])
    assert invite_uri in payload["attributes"]["post.logout.redirect.uris"].split("##")


def test_setup_keeps_every_listed_host_once() -> None:
    payload = _ui_payload_written("https://grm-chatbot.dor.gov.np/login")
    assert payload["redirectUris"] == [f"{o}/*" for o in ks.UI_ORIGINS]


def test_appointing_a_new_officer_explains_the_refusal() -> None:
    """The screenshot's path: create the account, then the email is refused."""
    from fastapi import HTTPException

    from ticketing.services import officer_admin as oa

    admin = MagicMock()
    admin.send_update_account.side_effect = KEYCLOAK_REFUSAL
    kc_user = {"id": "kc-1", "email": "adangelo.consultant@adb.org", "enabled": True}
    with patch.object(oa, "_keycloak_admin", return_value=admin), patch.object(
        oa, "_keycloak_find_user", return_value=kc_user
    ), patch.object(oa, "_keycloak_invite_email_options", return_value=("ticketing-ui", STAGING_INVITE)):
        with pytest.raises(HTTPException) as caught:
            oa.keycloak_create_user("adangelo.consultant@adb.org", "org_admin", "DOR")

    assert caught.value.status_code == 503
    assert STAGING_INVITE in caught.value.detail
    assert "--clients-only" in caught.value.detail
    assert "errorMessage" not in caught.value.detail


def _preflight(redirect_uris: list[str]) -> dict:
    from ticketing.services import officer_admin as oa

    admin = MagicMock()
    admin.connection.raw_get.return_value.json.return_value = {
        "enabled": True,
        "smtpServer": {"host": "smtp", "from": "grm@x", "user": "u", "password": "p"},
    }
    admin.get_clients.return_value = [{"clientId": "ticketing-ui", "redirectUris": redirect_uris}]
    with patch.object(oa, "keycloak_configured", return_value=True), patch.object(
        oa, "_keycloak_admin", return_value=admin
    ), patch.object(oa, "_keycloak_invite_email_options", return_value=("ticketing-ui", STAGING_INVITE)):
        return oa.keycloak_invite_preflight()


def test_preflight_fails_when_keycloak_would_refuse_the_redirect() -> None:
    result = _preflight(STAGING_REDIRECTS_BEFORE)
    assert result["ok"] is False
    assert "--clients-only" in result["message"]


def test_preflight_passes_once_the_redirect_is_allowed() -> None:
    result = _preflight([*STAGING_REDIRECTS_BEFORE, "https://nepal-gms-chatbot.facets-ai.com/*"])
    assert result["ok"] is True
