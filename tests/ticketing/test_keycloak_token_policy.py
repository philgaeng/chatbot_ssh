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

**And the session lengths (`GRM-111`, D-012).** The realm never set its idle timeout, so Keycloak's
default 30 minutes applied beside a 60-minute access token: the refresh token died half an hour before
the token it existed to renew, and every officer was signed out at about the hour. The order of the
numbers is the whole policy, so it is pinned as an order, not only as values.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ticketing.auth import keycloak_setup as ks

POLICY = {
    "revokeRefreshToken": True,
    "refreshTokenMaxReuse": 0,
    # D-012 — written on every run, never left to Keycloak's defaults.
    "accessTokenLifespan": 300,
    "ssoSessionIdleTimeout": 1800,
    "ssoSessionMaxLifespan": 28800,
}

# The officer UI renews an access token on the next request once it is within this many seconds of
# expiry (`isAccessTokenExpiringSoon(token, 60)` in channels/ticketing-ui/lib/api.ts).
UI_RENEWAL_LEAD_SECONDS = 60


def test_the_policy_is_one_use_per_refresh_token() -> None:
    assert ks.REVOKE_REFRESH_TOKEN is True
    assert ks.REFRESH_TOKEN_MAX_REUSE == 0, (
        "a reuse allowance lets a stolen token and the officer's own renewal both succeed — the "
        "cross-tab lock in oidc-auth.ts is what makes 0 safe, not a grace count"
    )


def test_the_access_token_is_renewable_inside_the_idle_window() -> None:
    """⭐ The rule that failed. A refresh token lives only as long as the idle window, so renewal
    near the access token's end needs the idle window to still be open then — with room to spare, so
    an officer who pauses between requests is not signed out while still well inside the window."""
    access, idle, max_ = ks.ACCESS_TOKEN_LIFESPAN, ks.SSO_SESSION_IDLE_TIMEOUT, ks.SSO_SESSION_MAX_LIFESPAN
    assert access + UI_RENEWAL_LEAD_SECONDS < idle, (
        f"access token {access}s must end well inside the {idle}s idle window, or renewal is attempted "
        "with a refresh token that has already expired (GRM-111)"
    )
    assert access * 4 <= idle, "a working officer should renew several times per idle window, not once"
    assert idle < max_, "the idle window is inside the maximum session, not beyond it"


def test_the_session_is_the_decided_one() -> None:
    """D-012's numbers. Changing one is a decision — record it there, then here."""
    assert (ks.ACCESS_TOKEN_LIFESPAN, ks.SSO_SESSION_IDLE_TIMEOUT, ks.SSO_SESSION_MAX_LIFESPAN) == (300, 1800, 28800)


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
    # …without dropping the invite-link lifespan it already set.
    assert payload["actionTokenGeneratedByAdminLifespan"] == ks.ACTION_TOKEN_ADMIN_LIFESPAN


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
