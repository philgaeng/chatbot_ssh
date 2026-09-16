# SPDX-License-Identifier: Apache-2.0

"""Server-side session refresh for password sign-in (`GRM-104`).

**The defect this closes.** Officers sign in with the email + password form, which the server runs
against `ticketing-api` — a **confidential** Keycloak client whose secret lives only on the server.
Silent refresh ran **in the browser**, posting straight to Keycloak as `ticketing-ui` (a *different*,
public client) with no secret. Keycloak refuses that twice over — the token's `azp` does not match,
and a confidential client's token cannot be refreshed without its credentials — so `doRefresh()`
returned null every time and every officer was signed out when their 1-hour access token expired.
`16_auth_keycloak.md` promises sessions of up to 8 h.

⭐ **This is the same mistake the sign-out path made and fixed** (`test_auth_logout.py`): a browser
cannot tell a confidential client from a public one, so choosing the credentials is the server's job.
Refresh was simply never given the same treatment.

**Why a test suite and not a one-line fix:** the existing frontend tests mocked `fetch` without
checking *where* it posted or *as which client*, so they passed for the whole life of the defect.
These tests pin the two properties that were missing — the credentials chosen, and the boundary.
"""
from __future__ import annotations

import base64
import json

import httpx
import pytest

from ticketing.services import auth_login
from ticketing.services.auth_login import AuthLoginError, refresh_with_refresh_token

SECRET = "the-client-secret"
TOKENS = {
    "access_token": "new-access",
    "id_token": "new-id",
    "refresh_token": "rotated-refresh",
    "expires_in": 3600,
    "token_type": "Bearer",
}


class _Resp:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = json.dumps(self._payload)

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self) -> dict:
        return self._payload


@pytest.fixture
def keycloak(monkeypatch: pytest.MonkeyPatch):
    """Patch the seams and capture every outbound POST."""
    calls: list[dict] = []
    reply = {"status": 200, "payload": dict(TOKENS)}
    monkeypatch.setattr(auth_login, "keycloak_configured", lambda: True)
    monkeypatch.setattr(auth_login, "_keycloak_realm_base", lambda: "http://keycloak:8080/realms/grm")
    monkeypatch.setattr(auth_login, "_api_client_secret", lambda: SECRET)

    def _post(url, data=None, headers=None, timeout=None):
        calls.append({"url": url, "data": dict(data or {})})
        return _Resp(reply["status"], reply["payload"])

    monkeypatch.setattr(auth_login.httpx, "post", _post)
    return calls, reply


def _jwt(claims: dict) -> str:
    def seg(d: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")

    return f"{seg({'alg': 'RS256'})}.{seg(claims)}.sig"


# ── Credentials: chosen by the client the token was issued to ─────────────────


def test_a_password_sign_in_token_is_refreshed_as_the_confidential_client_WITH_its_secret(keycloak) -> None:
    """⭐ The regression itself. This is the request the browser could never make."""
    calls, _ = keycloak
    tokens = refresh_with_refresh_token(_jwt({"azp": "ticketing-api"}))

    assert len(calls) == 1
    assert calls[0]["url"].endswith("/protocol/openid-connect/token")
    assert calls[0]["data"]["grant_type"] == "refresh_token"
    assert calls[0]["data"]["client_id"] == "ticketing-api"
    assert calls[0]["data"]["client_secret"] == SECRET
    assert tokens["access_token"] == "new-access"


def test_a_public_client_token_is_refreshed_WITHOUT_a_secret(keycloak) -> None:
    """⚠ Not symmetry for its own sake: Keycloak REJECTS a secret sent for a public client, so
    "always send it" is not a simpler correct answer — the same finding the sign-out path made."""
    calls, _ = keycloak
    refresh_with_refresh_token(_jwt({"azp": "ticketing-ui"}))

    assert calls[0]["data"]["client_id"] == "ticketing-ui"
    assert "client_secret" not in calls[0]["data"]


def test_an_undecodable_token_falls_back_to_the_confidential_client(keycloak) -> None:
    """Every real session comes from password sign-in, so that is the right default. A bad guess
    costs a refused refresh, never a granted one — Keycloak still validates the token."""
    calls, _ = keycloak
    refresh_with_refresh_token("not-a-jwt-at-all")
    assert calls[0]["data"]["client_id"] == "ticketing-api"


# ── The boundary: this endpoint grants tokens, so it refuses what it does not own ──


def test_a_token_issued_to_any_other_client_is_refused_before_keycloak_is_asked(keycloak) -> None:
    """⭐ The difference from sign-out, and why it is deliberate.

    Sign-out only ever *ends* a session, so it forwards whatever client the token names. Refresh
    *grants* tokens. The `azp` it reads is an unverified decode, and this endpoint is reachable
    without authentication by design — so it must not become a way to exercise refresh for
    arbitrary clients in the realm. Only the two clients that issue officer sessions are accepted,
    and anything else never reaches Keycloak.
    """
    calls, _ = keycloak
    with pytest.raises(AuthLoginError) as exc:
        refresh_with_refresh_token(_jwt({"azp": "realm-management"}))

    assert exc.value.status_code == 401
    assert exc.value.code == "session_expired"
    assert calls == [], "a token for a foreign client must be refused without calling Keycloak"


def test_our_secret_is_never_attached_to_a_request_for_another_client(keycloak) -> None:
    """The credential boundary stated as its own property, so a future allowlist edit that adds a
    client cannot silently start lending it the confidential client's secret."""
    calls, _ = keycloak
    for azp in ("ticketing-ui", "ticketing-api"):
        refresh_with_refresh_token(_jwt({"azp": azp}))
    for call in calls:
        if call["data"]["client_id"] != "ticketing-api":
            assert "client_secret" not in call["data"]


def test_an_empty_token_is_rejected_before_any_request(keycloak) -> None:
    calls, _ = keycloak
    for bad in ("", "   "):
        with pytest.raises(AuthLoginError) as exc:
            refresh_with_refresh_token(bad)
        assert exc.value.status_code == 422
    assert calls == []


# ── Failure modes map to what the browser should do next ──────────────────────


def test_an_expired_or_rotated_grant_is_a_401_so_the_browser_signs_out_cleanly(keycloak) -> None:
    """400 invalid_grant is the ordinary end of a session — expired, revoked, or a refresh token
    already rotated away. It is a sign-out, not a server fault, and must not read as one."""
    _, reply = keycloak
    reply.update(status=400, payload={"error": "invalid_grant", "error_description": "Token is not active"})
    with pytest.raises(AuthLoginError) as exc:
        refresh_with_refresh_token(_jwt({"azp": "ticketing-api"}))
    assert (exc.value.status_code, exc.value.code) == (401, "session_expired")


@pytest.mark.parametrize("error", ["invalid_client", "unauthorized_client"])
def test_a_misconfigured_client_is_a_503_not_a_quiet_sign_out(keycloak, error: str) -> None:
    """⚠ If the client secret is wrong, EVERY officer is signed out at the hour. Reporting that as
    an ordinary expired session would hide an outage behind a normal-looking prompt to sign in."""
    _, reply = keycloak
    reply.update(status=401, payload={"error": error, "error_description": "Invalid client credentials"})
    with pytest.raises(AuthLoginError) as exc:
        refresh_with_refresh_token(_jwt({"azp": "ticketing-api"}))
    assert (exc.value.status_code, exc.value.code) == (503, "auth_unavailable")


def test_an_unreachable_keycloak_is_a_503(keycloak, monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_a, **_k):
        raise httpx.ConnectError("keycloak down")

    monkeypatch.setattr(auth_login.httpx, "post", _boom)
    with pytest.raises(AuthLoginError) as exc:
        refresh_with_refresh_token(_jwt({"azp": "ticketing-api"}))
    assert exc.value.status_code == 503


def test_a_success_with_no_access_token_is_not_treated_as_success(keycloak) -> None:
    """A 200 that carries no access token would otherwise surface as a KeyError — a 500 — or worse,
    as an empty session the browser stores and then fails on."""
    _, reply = keycloak
    reply.update(status=200, payload={"token_type": "Bearer"})
    with pytest.raises(AuthLoginError) as exc:
        refresh_with_refresh_token(_jwt({"azp": "ticketing-api"}))
    assert exc.value.status_code == 502


def test_neither_the_token_nor_the_secret_is_ever_logged(keycloak, caplog) -> None:
    """Every failure path logs. None of them may carry the credential or the secret."""
    token = _jwt({"azp": "ticketing-api", "marker": "do-not-log-me"})
    _, reply = keycloak
    caplog.set_level("DEBUG")
    for status, payload in (
        (400, {"error": "invalid_grant"}),
        (401, {"error": "invalid_client"}),
        (500, {"error": "server_error"}),
    ):
        reply.update(status=status, payload=payload)
        with pytest.raises(AuthLoginError):
            refresh_with_refresh_token(token)
    assert token not in caplog.text
    assert SECRET not in caplog.text


def test_a_reused_refresh_token_is_logged_as_a_warning_an_operator_can_find(keycloak, caplog) -> None:
    """`GRM-105`. With revocation on, a second use of a refresh token ends the whole session — a
    stolen token replayed, or two tabs that raced past the renewal lock. Either way it is not the
    ordinary end of a session, and must not be filed at INFO beside it. Still a plain 401 to the
    browser, and still no token in the log."""
    token = _jwt({"azp": "ticketing-api", "marker": "do-not-log-me"})
    _, reply = keycloak
    reply.update(status=400, payload={"error": "invalid_grant", "error_description": "Maximum allowed refresh token reuse exceeded"})
    caplog.set_level("DEBUG", logger="ticketing.services.auth_login")

    with pytest.raises(AuthLoginError) as exc:
        refresh_with_refresh_token(token)

    assert (exc.value.status_code, exc.value.code) == (401, "session_expired")
    warnings = [r for r in caplog.records if r.levelname == "WARNING" and "reused" in r.getMessage()]
    assert warnings, "a refused reuse must be logged at WARNING"
    assert token not in caplog.text and SECRET not in caplog.text


def test_an_ordinary_expiry_is_not_reported_as_a_reuse(keycloak, caplog) -> None:
    """The control for the test above: a session that simply ran out must not cry wolf, or the
    warning gets ignored the day it matters."""
    _, reply = keycloak
    reply.update(status=400, payload={"error": "invalid_grant", "error_description": "Token is not active"})
    caplog.set_level("DEBUG", logger="ticketing.services.auth_login")

    with pytest.raises(AuthLoginError):
        refresh_with_refresh_token(_jwt({"azp": "ticketing-api"}))

    assert not [r for r in caplog.records if r.levelname == "WARNING"]


def test_the_public_client_id_matches_the_realm_setup() -> None:
    """The allowlist names `ticketing-ui` without importing the setup module. Pin that the two
    cannot drift apart — a renamed client would otherwise refuse every refresh as 'foreign'."""
    # Read from source, not imported: keycloak_setup pulls in python-keycloak at import time, and a
    # drift guard that only runs where that package happens to be installed is a guard that
    # silently stops running.
    import re
    from pathlib import Path

    source = (Path(auth_login.__file__).parents[1] / "auth" / "keycloak_setup.py").read_text()
    realm = dict(re.findall(r'^(CLIENT_UI|CLIENT_API)\s*=\s*"([^"]+)"', source, re.M))
    assert realm, "could not find CLIENT_UI / CLIENT_API in keycloak_setup.py — the guard itself is broken"
    assert auth_login.CLIENT_UI == realm["CLIENT_UI"]
    assert auth_login.CLIENT_API == realm["CLIENT_API"]


# ── The endpoint ────────────────────────────────────────────────────────────────


def test_the_endpoint_returns_only_token_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    """⭐ The response is the boundary between Keycloak's reply and the browser. Whatever else
    Keycloak returns — session state, scopes, or anything a future change leaks into the dict —
    must not pass through. Pinned against a service result deliberately carrying a secret."""
    from ticketing.api.routers import auth as auth_router

    monkeypatch.setattr(
        auth_router,
        "refresh_with_refresh_token",
        lambda _t: {**TOKENS, "client_secret": SECRET, "session_state": "abc", "not-before-policy": 0},
    )
    body = auth_router.auth_refresh(auth_router.RefreshRequest(refresh_token=_jwt({"azp": "ticketing-api"})))
    dumped = body.model_dump()

    assert set(dumped) == {"access_token", "id_token", "refresh_token", "expires_in", "token_type"}
    assert SECRET not in json.dumps(dumped)
    assert dumped["refresh_token"] == "rotated-refresh", "the rotated refresh token must reach the browser"


def test_an_ended_session_is_a_401_not_a_200(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unlike sign-out, which always answers 200, a failed refresh MUST fail: the browser keys off
    `resp.ok`, and a 200 here would leave it holding an expired access token."""
    from fastapi import HTTPException

    from ticketing.api.routers import auth as auth_router

    def _raise(_t: str) -> None:
        raise AuthLoginError("session_expired", "Your session has ended. Please sign in again.", 401)

    monkeypatch.setattr(auth_router, "refresh_with_refresh_token", _raise)
    with pytest.raises(HTTPException) as exc:
        auth_router.auth_refresh(auth_router.RefreshRequest(refresh_token=_jwt({"azp": "ticketing-api"})))
    assert exc.value.status_code == 401


def test_the_endpoint_is_not_jwt_gated() -> None:
    """By definition the access token has expired when this is called. Requiring a valid one would
    make the endpoint unusable in the one situation it exists for. The refresh token IS the credential."""
    import inspect

    from ticketing.api.routers import auth as auth_router

    assert list(inspect.signature(auth_router.auth_refresh).parameters) == ["body"]
