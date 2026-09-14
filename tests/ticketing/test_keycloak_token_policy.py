# SPDX-License-Identifier: Apache-2.0
"""
The realm revokes a refresh token once it has been used (`GRM-105`).

**Measured on Keycloak 2026-09-14, before this change:** a spent refresh token was ACCEPTED again —
`keycloak_setup.py` never set `revokeRefreshToken`, so every realm it built ran Keycloak's default
(off), staging and production included. `GRM-104` made that matter: `/api/v1/auth/refresh` supplies
the confidential client's secret to whoever presents a token, so a leaked one was an 8-hour session.

**Measured with revocation on:** a second use is refused AND ends the whole session — the rightful
holder's fresh token too. That is what turns a replayed theft into a visible sign-out, and it is also
why the officer UI must serialise renewal across tabs before this policy reaches a realm.

These pin the policy on BOTH paths that write it: a new realm, and — the one that reaches staging and
production — an update to an existing one.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ticketing.auth import keycloak_setup as ks

POLICY = {"revokeRefreshToken": True, "refreshTokenMaxReuse": 0}


def test_the_policy_is_one_use_per_refresh_token() -> None:
    assert ks.REVOKE_REFRESH_TOKEN is True
    assert ks.REFRESH_TOKEN_MAX_REUSE == 0, (
        "a reuse allowance lets a stolen token and the officer's own renewal both succeed — the "
        "cross-tab lock in oidc-auth.ts is what makes 0 safe, not a grace count"
    )


def test_a_new_realm_is_created_with_it() -> None:
    master = MagicMock()
    master.get_realms.return_value = []
    ks.setup_realm(master)
    payload = master.create_realm.call_args.args[0]
    assert {k: payload.get(k) for k in POLICY} == POLICY


def test_an_existing_realm_is_updated_to_it() -> None:
    """⭐ The path that matters. The create payload never reaches a realm that already exists, and
    every realm we run already exists."""
    admin = MagicMock()
    ks.setup_realm_token_lifespans(admin)
    realm, payload = admin.update_realm.call_args.args
    assert realm == ks.REALM
    assert {k: payload.get(k) for k in POLICY} == POLICY
    # …without dropping the lifespans it already set.
    assert payload["accessTokenLifespan"] == ks.ACCESS_TOKEN_LIFESPAN
    assert payload["ssoSessionMaxLifespan"] == ks.SSO_SESSION_MAX_LIFESPAN


def test_token_policy_only_touches_nothing_else(monkeypatch: pytest.MonkeyPatch) -> None:
    """A live realm gets the policy and nothing more: the full run also rewrites demo officers,
    SMTP, clients and the theme, none of which a token-policy rollout should change."""
    admin = MagicMock()
    monkeypatch.setattr(ks, "get_settings", lambda: MagicMock(keycloak_admin_url="http://keycloak:8080/keycloak"))
    monkeypatch.setattr(ks, "_realm_admin", lambda: admin)
    monkeypatch.setattr(ks, "_master_admin", MagicMock(side_effect=AssertionError("master admin must not be used")))
    for step in (
        "setup_realm_event_logging", "setup_realm_smtp", "setup_realm_login_theme", "setup_user_profile_policy",
        "setup_officer_phone_profile", "setup_clients", "setup_token_mappers", "setup_demo_users",
    ):
        monkeypatch.setattr(ks, step, MagicMock(side_effect=AssertionError(f"{step} must not run")))

    ks.main(["--token-policy-only"])

    assert admin.update_realm.call_count == 1
    assert {k: admin.update_realm.call_args.args[1].get(k) for k in POLICY} == POLICY
