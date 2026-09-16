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


def _jwt(claims: dict) -> str:
    import base64
    import json

    def seg(d: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")

    return f"{seg({'alg': 'RS256'})}.{seg(claims)}.sig"


def test_a_confidential_client_token_carries_the_client_secret(keycloak) -> None:
    """⭐ The whole point. Without this the request is the one that was silently failing."""
    calls, _ = keycloak
    logout_with_refresh_token(_jwt({"azp": "ticketing-api"}))

    assert len(calls) == 1
    assert calls[0]["url"].endswith("/protocol/openid-connect/logout")
    assert calls[0]["data"]["client_secret"] == "the-client-secret"
    assert calls[0]["data"]["client_id"] == "ticketing-api"


def test_a_public_client_token_is_revoked_WITHOUT_a_secret(keycloak) -> None:
    """⚠ Not symmetry for its own sake — Keycloak REJECTS a secret sent for a public client,
    so "always send it" is not a simpler correct answer."""
    calls, _ = keycloak
    logout_with_refresh_token(_jwt({"azp": "ticketing-ui"}))

    assert calls[0]["data"]["client_id"] == "ticketing-ui"
    assert "client_secret" not in calls[0]["data"]


def test_the_azp_equalling_the_configured_client_id_still_gets_a_secret(keycloak) -> None:
    """⭐ THE REGRESSION. The first fix routed on `azp != NEXT_PUBLIC_OIDC_CLIENT_ID`, assuming
    that variable names the PUBLIC client. On staging it is `ticketing-api` — the confidential
    one — so the test compared a value against itself, never fired, and the bug survived a
    deploy while looking fixed. Equality must NOT mean "no secret needed"."""
    calls, _ = keycloak
    logout_with_refresh_token(_jwt({"azp": "ticketing-api"}))
    assert calls[0]["data"].get("client_secret") == "the-client-secret"


def test_an_undecodable_token_falls_back_to_the_confidential_client(keycloak) -> None:
    """Fail towards the client that needs credentials: a missing secret is a guaranteed
    rejection, while an unnecessary one fails no worse than guessing the other way."""
    calls, _ = keycloak
    logout_with_refresh_token("not-a-jwt-at-all")
    assert calls[0]["data"]["client_id"] == "ticketing-api"
    assert calls[0]["data"]["client_secret"] == "the-client-secret"


def test_an_already_invalid_token_is_a_SOFT_NO_not_a_success(keycloak) -> None:
    """⭐ The hardening. Keycloak answers 400 for a token already expired or spent — and that is
    NOT proof the session ended: a refresh token can expire while the SSO session it belongs to
    is still alive, since their lifespans are configured separately.

    Reporting success here would send the browser down the same-origin path and leave that
    session — plus Keycloak's cookie, which only the front channel clears — intact. So it must
    not raise (there is nothing wrong) and must not claim a revocation either.
    """
    _, response = keycloak
    response["status"] = 400
    response["payload"] = {"error": "invalid_grant"}
    assert logout_with_refresh_token(REFRESH) is False


@pytest.mark.parametrize("status", [200, 204])
def test_only_a_confirmed_revocation_returns_true(keycloak, status: int) -> None:
    _, response = keycloak
    response["status"] = status
    assert logout_with_refresh_token(REFRESH) is True


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
    The client clears its storage regardless, so the wrong direction to fail is 'still logged in'."""
    from ticketing.api.routers import auth as auth_router

    def _raise(_token: str) -> None:
        raise AuthLoginError("logout_failed", "nope", 502)

    monkeypatch.setattr(auth_router, "logout_with_refresh_token", _raise)
    result = auth_router.auth_logout(auth_router.LogoutRequest(refresh_token=REFRESH))
    assert result.message == "Signed out."


def test_a_failed_revoke_reports_revoked_false_in_the_BODY(monkeypatch: pytest.MonkeyPatch) -> None:
    """⭐ The flag the client falls back on, and why it cannot be the HTTP status.

    The status stays 200 by design (above), so `resp.ok` is always true and could never
    trigger the fallback. Putting the outcome in the body keeps both properties: the sign-out
    never fails, and the failure is never hidden. Without this the client would take the
    same-origin redirect while the session was still live on Keycloak.
    """
    from ticketing.api.routers import auth as auth_router

    def _raise(_token: str) -> None:
        raise AuthLoginError("logout_failed", "nope", 502)

    monkeypatch.setattr(auth_router, "logout_with_refresh_token", _raise)
    assert auth_router.auth_logout(auth_router.LogoutRequest(refresh_token=REFRESH)).revoked is False


def test_a_successful_revoke_reports_revoked_true(monkeypatch: pytest.MonkeyPatch) -> None:
    from ticketing.api.routers import auth as auth_router

    monkeypatch.setattr(auth_router, "logout_with_refresh_token", lambda _t: True)
    assert auth_router.auth_logout(auth_router.LogoutRequest(refresh_token=REFRESH)).revoked is True


def test_nothing_to_revoke_is_reported_as_revoked_false(monkeypatch: pytest.MonkeyPatch) -> None:
    """⚠ The endpoint must PASS THROUGH the soft no rather than flattening it to success.
    `revoked` answers one question — 'is it safe to skip the front-channel logout?' — and the
    answer here is no."""
    from ticketing.api.routers import auth as auth_router

    monkeypatch.setattr(auth_router, "logout_with_refresh_token", lambda _t: False)
    assert auth_router.auth_logout(auth_router.LogoutRequest(refresh_token=REFRESH)).revoked is False


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
