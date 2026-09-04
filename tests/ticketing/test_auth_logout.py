# SPDX-License-Identifier: Apache-2.0

"""Server-side refresh-token revocation for the confidential API client.

**The defect this closes.** The browser posted the revoke straight to Keycloak with `client_id`
alone. That is correct for `ticketing-ui`, a *public* client — and impossible for `ticketing-api`,
which is *confidential* and requires a `client_secret` a browser must never hold. Every revoke on
the password-login path was rejected with `invalid_client_credentials`, and the browser discarded
the result by design (`void fetch`, "best-effort"), so nothing surfaced it until realm event logging
was enabled and recorded the first real logout.

**What the impact actually is**, because the tests are written to that and not to the alarm: after an
ordinary logout the front-channel call ends the session anyway and this is redundant. It is
load-bearing on the *stale session* path, which skips the front channel by design — there it is the
only thing that ends the session.
"""
from __future__ import annotations

import httpx
import pytest

from ticketing.services import auth_login
from ticketing.services.auth_login import AuthLoginError, logout_with_refresh_token

REFRESH = "a-refresh-token-value"


class _Resp:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = str(self._payload)

    def json(self) -> dict:
        return self._payload


@pytest.fixture
def keycloak(monkeypatch: pytest.MonkeyPatch):
    """Patch the seams, capture the outbound POST."""
    calls: list[dict] = []
    monkeypatch.setattr(auth_login, "keycloak_configured", lambda: True)
    monkeypatch.setattr(auth_login, "_keycloak_realm_base", lambda: "http://keycloak:8080/realms/grm")
    monkeypatch.setattr(auth_login, "_api_client_secret", lambda: "the-client-secret")

    def _post(url, data=None, headers=None, timeout=None):
        calls.append({"url": url, "data": data})
        return _Resp(calls_response["status"], calls_response.get("payload"))

    calls_response = {"status": 204}
    monkeypatch.setattr(auth_login.httpx, "post", _post)
    return calls, calls_response


def test_the_revoke_carries_the_client_secret(keycloak) -> None:
    """⭐ The whole point. Without this the request is the one that was silently failing."""
    calls, _ = keycloak
    logout_with_refresh_token(REFRESH)

    assert len(calls) == 1
    assert calls[0]["url"].endswith("/protocol/openid-connect/logout")
    assert calls[0]["data"]["client_secret"] == "the-client-secret"
    assert calls[0]["data"]["refresh_token"] == REFRESH
    assert calls[0]["data"]["client_id"]


def test_an_already_invalid_token_counts_as_signed_out(keycloak) -> None:
    """Keycloak answers 400 for a token already expired or spent. That is the desired END STATE,
    not a failure — treating it as one would make a retry loop out of a successful sign-out."""
    _, response = keycloak
    response["status"] = 400
    response["payload"] = {"error": "invalid_grant"}
    logout_with_refresh_token(REFRESH)  # must not raise


@pytest.mark.parametrize("status", [200, 204])
def test_success_statuses_do_not_raise(keycloak, status: int) -> None:
    _, response = keycloak
    response["status"] = status
    logout_with_refresh_token(REFRESH)


def test_a_rejected_revoke_raises_so_the_caller_can_log_it(keycloak) -> None:
    _, response = keycloak
    response["status"] = 401
    response["payload"] = {"error": "invalid_client_credentials"}
    with pytest.raises(AuthLoginError) as exc:
        logout_with_refresh_token(REFRESH)
    assert exc.value.code == "logout_failed"


def test_an_unreachable_keycloak_raises_rather_than_pretending(keycloak, monkeypatch) -> None:
    def _boom(*a, **k):
        raise httpx.ConnectError("no route")

    monkeypatch.setattr(auth_login.httpx, "post", _boom)
    with pytest.raises(AuthLoginError) as exc:
        logout_with_refresh_token(REFRESH)
    assert exc.value.code == "auth_unavailable"


def test_an_empty_token_is_rejected_before_any_request(keycloak) -> None:
    calls, _ = keycloak
    for value in ("", "   "):
        with pytest.raises(AuthLoginError):
            logout_with_refresh_token(value)
    assert calls == [], "no request should leave for an empty token"


def test_the_token_is_never_logged(keycloak, caplog) -> None:
    """A refresh token in a log is a credential in a log — the finding D-62 was raised for."""
    _, response = keycloak
    response["status"] = 401
    response["payload"] = {"error": "invalid_client_credentials"}
    with caplog.at_level("DEBUG"):
        with pytest.raises(AuthLoginError):
            logout_with_refresh_token(REFRESH)
    assert REFRESH not in caplog.text


# ── The endpoint ────────────────────────────────────────────────────────────────


def test_the_endpoint_answers_200_even_when_the_revoke_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """⚠ Deliberate. A sign-out that reports failure invites a UI that keeps the user signed in.
    The client clears its storage regardless, so the wrong direction to fail is 'still logged in'.
    The failure is logged, and shows up as LOGOUT_ERROR in the realm event log."""
    from ticketing.api.routers import auth as auth_router

    def _raise(_token: str) -> None:
        raise AuthLoginError("logout_failed", "nope", 502)

    monkeypatch.setattr(auth_router, "logout_with_refresh_token", _raise)
    result = auth_router.auth_logout(auth_router.LogoutRequest(refresh_token=REFRESH))
    assert result.message == "Signed out."


def test_the_endpoint_is_not_jwt_gated() -> None:
    """The refresh token IS the credential, and the access token is routinely gone by sign-out.
    Requiring one would make this fail in the stale-session case it exists for."""
    import inspect

    from ticketing.api.routers import auth as auth_router

    sig = inspect.signature(auth_router.auth_logout)
    assert list(sig.parameters) == ["body"], (
        "auth_logout must take only its body — adding an auth dependency breaks the one path "
        "this endpoint exists to serve"
    )
