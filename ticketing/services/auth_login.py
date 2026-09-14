# SPDX-License-Identifier: Apache-2.0

"""Officer login and password reset (Keycloak + Messaging API)."""
from __future__ import annotations

import logging
import re
import time
from typing import Any

import httpx
from jose import JWTError, jwt

from ticketing.config.settings import get_settings
from ticketing.services.officer_admin import _keycloak_admin, keycloak_configured

logger = logging.getLogger(__name__)

RESET_PURPOSE = "password_reset"
RESET_TTL_SECONDS = 3600
CLIENT_API = "ticketing-api"
# The public, browser-side client. Named here rather than imported from keycloak_setup so this
# module stays import-light; `test_the_public_client_id_matches_the_realm_setup` pins that the two
# cannot drift apart.
CLIENT_UI = "ticketing-ui"

_ALLOWED_REDIRECT = re.compile(
    r"^https://("
    r"grm-auth\.[\w.-]*facets-ai\.com"
    r"|grm\.stage\.facets-ai\.com"
    r"|grm\.facets-ai\.com"
    r"|grm-chatbot\.dor\.gov\.np"
    r"|grm\.[\w.-]*dor\.gov\.np"
    r")$"
    r"|^http://localhost:\d+$",
    re.I,
)


class AuthLoginError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _validate_redirect_base(redirect_base: str) -> str:
    base = redirect_base.strip().rstrip("/")
    if not base or not _ALLOWED_REDIRECT.match(base):
        raise AuthLoginError(
            "invalid_redirect",
            "Invalid application URL for password reset.",
            422,
        )
    return base


def _issuer() -> str:
    settings = get_settings()
    issuer = (settings.keycloak_issuer or "").rstrip("/")
    if not issuer:
        raise AuthLoginError("auth_unavailable", "Authentication is not configured.", 503)
    return issuer


def _keycloak_realm_base() -> str:
    """
    Keycloak realm URL reachable from the ticketing API container.

    JWT verification uses `keycloak_issuer` (browser-facing `iss` claim). Token
    exchange must use Docker-internal DNS — same pattern as KEYCLOAK_JWKS_URL.
    """
    settings = get_settings()
    if settings.keycloak_token_issuer:
        return settings.keycloak_token_issuer.rstrip("/")

    jwks = (settings.keycloak_jwks_url or "").strip()
    if jwks and "/protocol/openid-connect/" in jwks:
        return jwks.split("/protocol/openid-connect/", 1)[0].rstrip("/")

    admin = (settings.keycloak_admin_url or "").rstrip("/")
    if admin:
        return f"{admin}/realms/grm"

    return _issuer()


def _api_client_secret() -> str:
    settings = get_settings()
    if settings.keycloak_client_secret:
        return settings.keycloak_client_secret
    if not keycloak_configured():
        raise AuthLoginError("auth_unavailable", "Authentication is not configured.", 503)
    admin = _keycloak_admin()
    from ticketing.auth.keycloak_setup import _get_client_uuid

    api_uuid = _get_client_uuid(admin, CLIENT_API)
    if not api_uuid:
        raise AuthLoginError("auth_unavailable", "Keycloak API client is not configured.", 503)
    secret = admin.get_client_secrets(api_uuid)
    value = (secret or {}).get("value") or ""
    if not value:
        raise AuthLoginError("auth_unavailable", "Keycloak API client secret is missing.", 503)
    return value


def _find_keycloak_user(email: str) -> dict[str, Any] | None:
    admin = _keycloak_admin()
    for query in ({"username": email, "exact": True}, {"email": email, "exact": True}):
        found = admin.get_users(query)
        if found:
            return found[0]
    return None


def _names_from_email(email: str) -> tuple[str, str]:
    local = email.split("@", 1)[0]
    parts = local.replace(".", " ").replace("-", " ").split()
    first = parts[0].title() if parts else local
    last = parts[-1].title() if len(parts) > 1 else "Officer"
    return first, last


def _ensure_keycloak_profile_ready(admin, user: dict[str, Any], email: str) -> None:
    """
    Keycloak rejects password grant with 'Account is not fully set up' when required
    declarative profile fields are missing (email, name, phone_number on grm realm).
    """
    uid = user["id"]
    first, last = _names_from_email(email)
    attrs = {k: list(v) for k, v in (user.get("attributes") or {}).items()}
    phone = (attrs.get("phone_number") or [""])[0].strip()

    payload: dict[str, Any] = {"emailVerified": True}
    changed = False

    if not user.get("email"):
        changed = True
    if not user.get("firstName"):
        changed = True
    if not user.get("lastName"):
        changed = True
    if len(phone) < 8:
        # Placeholder until officer completes profile in Settings (Keycloak requires min 8).
        attrs["phone_number"] = ["9800000000"]
        changed = True

    if changed:
        payload["email"] = user.get("email") or email
        payload["firstName"] = user.get("firstName") or first
        payload["lastName"] = user.get("lastName") or last
        if attrs:
            payload["attributes"] = attrs
        # Do not clear Keycloak invite onboarding (UPDATE_PASSWORD) here.
        admin.update_user(uid, payload)


def _password_token_request(
    token_url: str,
    client_id: str,
    client_secret: str,
    username: str,
    password: str,
) -> httpx.Response:
    return httpx.post(
        token_url,
        data={
            "grant_type": "password",
            "client_id": client_id,
            "client_secret": client_secret,
            "username": username,
            "password": password,
            "scope": "openid email profile",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15.0,
    )


def _parse_token_error(resp: httpx.Response) -> tuple[str, str]:
    try:
        body = resp.json()
        return str(body.get("error") or ""), str(body.get("error_description") or body.get("error") or "")
    except Exception:
        return "", resp.text[:200]


def _refresh_token_client(refresh_token: str) -> str | None:
    """The `azp` a refresh token was issued to, or None if it cannot be read.

    ⚠ **Unverified decode, deliberately.** We are not trusting this claim for authorisation —
    Keycloak still validates the token. It only selects which credentials to present, and a
    wrong guess costs a failed revoke, not a granted one.
    """
    try:
        return str(jwt.get_unverified_claims(refresh_token).get("azp") or "") or None
    except (JWTError, Exception):  # noqa: B014 - jose raises several unrelated types
        return None


def logout_with_refresh_token(refresh_token: str) -> bool:
    """Revoke a refresh token, choosing credentials by the client that was issued it.

    **Returns True only when Keycloak confirms it ended the session.** The caller uses that to
    decide whether the same-origin redirect is enough or whether the browser must still make
    the front-channel Keycloak call.

    ⭐ **This is the server's job because only the server knows which clients are confidential.**
    `ticketing-api` needs a `client_secret`; `ticketing-ui` is public and must NOT be sent one.
    The browser cannot tell them apart, and two attempts to let it try both failed:

    1. Posting straight to Keycloak with `client_id` alone — correct for the public client,
       rejected with `invalid_client_credentials` for the confidential one.
    2. Routing on `azp != NEXT_PUBLIC_OIDC_CLIENT_ID` — which assumed that variable names the
       *public* client. On the staging deployment it is `ticketing-api`, the confidential one,
       so the test compared a value against itself and never fired.

    Both were invisible from the browser, which discards the result by design; both were found
    in the Keycloak realm event log.

    **Impact, stated narrowly:** after an ordinary logout the front-channel call ends the session
    anyway, so this is redundant. It is load-bearing on the *stale session* path, which skips the
    front channel by design — there this is the only thing that ends the session.

    Raises `AuthLoginError` so the caller can log it; sign-out must never be blocked by it.
    """
    if not keycloak_configured():
        raise AuthLoginError("auth_unavailable", "Authentication is not configured.", 503)
    if not refresh_token or not refresh_token.strip():
        raise AuthLoginError("invalid_token", "A refresh token is required.", 422)

    settings = get_settings()
    confidential_client = settings.keycloak_client_id
    issued_to = _refresh_token_client(refresh_token) or confidential_client

    data: dict[str, str] = {"client_id": issued_to, "refresh_token": refresh_token}
    if issued_to == confidential_client:
        # ⚠ Only the confidential client takes a secret. Sending one for a PUBLIC client is
        # itself rejected, so this cannot be "just always send it".
        data["client_secret"] = _api_client_secret()

    try:
        resp = httpx.post(
            f"{_keycloak_realm_base()}/protocol/openid-connect/logout",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10.0,
        )
    except httpx.HTTPError as exc:
        logger.warning("Keycloak logout request failed: %s", exc)
        raise AuthLoginError("auth_unavailable", "Sign-out service is unavailable.", 503) from exc

    if resp.status_code in (200, 204):
        return True

    if resp.status_code == 400:
        # ⚠ "Already invalid or expired" is NOT "the session is gone", and conflating them is a
        # real hole: a refresh token can expire while the SSO session it belongs to is still
        # alive, because their lifespans are configured separately. Reporting success here would
        # send the browser down the same-origin path and leave that session — and Keycloak's
        # cookie, which only the front channel clears — intact. So this is a soft NO: nothing
        # was revoked, let the caller fall back.
        err, desc = _parse_token_error(resp)
        logger.info(
            "Keycloak logout: nothing to revoke for client %s (%s) — falling back",
            issued_to,
            err or desc,
        )
        return False

    err, desc = _parse_token_error(resp)
    # ⚠ Never log the token. The grievance/user id is in the caller's own request context.
    logger.warning(
        "Keycloak logout rejected (%s) for client %s: %s", resp.status_code, issued_to, err or desc
    )
    raise AuthLoginError("logout_failed", "Could not sign out on the server.", 502)


def refresh_with_refresh_token(refresh_token: str) -> dict[str, Any]:
    """Exchange a refresh token for a fresh set, as the client the token was issued to.

    ⭐ **Why this exists (`GRM-104`).** Officers sign in with the email + password form, which runs
    against `ticketing-api` — a **confidential** client. Refresh used to run in the browser, posting
    straight to Keycloak as `ticketing-ui` with no secret: the wrong client AND no credentials, so it
    could never succeed, and every officer was signed out when the 1-hour access token expired
    (`16_auth_keycloak.md` promises up to 8 h). It is the same mistake `logout_with_refresh_token`
    documents making and fixing — only the server knows which clients are confidential.

    ⚠ **A deliberate difference from sign-out: an allowlist.** Sign-out only *ends* sessions, so it
    forwards whatever client the token names. Refresh *grants* tokens, the `azp` it reads is an
    unverified decode, and the endpoint is unauthenticated by design. So only the two clients that
    issue officer sessions are accepted; anything else is refused before Keycloak is asked, and the
    confidential client's secret is only ever attached to that client's own tokens.

    Raises `AuthLoginError`:
      * 401 `session_expired`  — the ordinary end of a session (expired, revoked, rotated away)
      * 503 `auth_unavailable` — Keycloak unreachable, or the client credentials are wrong. ⚠ The
        second must NOT look like an expired session: a bad secret signs out every officer at the
        hour, and a normal-looking "sign in again" would hide that outage.
      * 422 `invalid_token`    — nothing to refresh
    """
    if not keycloak_configured():
        raise AuthLoginError("auth_unavailable", "Authentication is not configured.", 503)
    if not refresh_token or not refresh_token.strip():
        raise AuthLoginError("invalid_token", "A refresh token is required.", 422)

    settings = get_settings()
    confidential_client = settings.keycloak_client_id
    issued_to = _refresh_token_client(refresh_token) or confidential_client

    if issued_to not in {confidential_client, CLIENT_UI}:
        # ⚠ Never log the token. The client name is not a secret and is what an operator needs.
        logger.warning("Refresh refused: token was issued to an unexpected client %r", issued_to)
        raise AuthLoginError("session_expired", "Your session has ended. Please sign in again.", 401)

    data: dict[str, str] = {
        "grant_type": "refresh_token",
        "client_id": issued_to,
        "refresh_token": refresh_token,
    }
    if issued_to == confidential_client:
        # ⚠ Only the confidential client takes a secret; Keycloak rejects one sent for a public client.
        data["client_secret"] = _api_client_secret()

    try:
        resp = httpx.post(
            f"{_keycloak_realm_base()}/protocol/openid-connect/token",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15.0,
        )
    except httpx.HTTPError as exc:
        logger.warning("Keycloak refresh request failed: %s", exc.__class__.__name__)
        raise AuthLoginError("auth_unavailable", "Sign-in service is temporarily unavailable.", 503) from exc

    if resp.is_success:
        tokens = resp.json()
        if not isinstance(tokens, dict) or not tokens.get("access_token"):
            logger.error("Keycloak refresh returned success without an access token")
            raise AuthLoginError("auth_unavailable", "Sign-in service returned an unexpected response.", 502)
        return tokens

    err, desc = _parse_token_error(resp)
    if err in ("invalid_client", "unauthorized_client"):
        logger.error("Keycloak client authentication failed on refresh (%s): %s", issued_to, err)
        raise AuthLoginError(
            "auth_unavailable",
            "Sign-in service is misconfigured. Contact your administrator.",
            503,
        )
    if resp.status_code in (400, 401):
        if "reuse" in (desc or "").lower():
            # ⚠ `GRM-105`: a refresh token was presented a SECOND time. With revocation on, Keycloak
            # ends the whole session when that happens — measured, for the rightful holder too — so
            # this is either two tabs that raced past the browser's renewal lock, or a stolen token
            # being replayed. Both deserve a line an operator can find; neither logs the token.
            logger.warning(
                "Keycloak refresh: a refresh token was reused (client %s) — Keycloak ended the session. "
                "Possible replay of a stolen token, or a renewal race between tabs.",
                issued_to,
            )
        else:
            logger.info("Keycloak refresh: grant rejected for client %s (%s)", issued_to, err or resp.status_code)
        raise AuthLoginError("session_expired", "Your session has ended. Please sign in again.", 401)

    logger.warning("Keycloak refresh failed (%s) for client %s: %s", resp.status_code, issued_to, err)
    raise AuthLoginError("auth_unavailable", "Sign-in service is temporarily unavailable.", 502)


def login_with_password(email: str, password: str) -> dict[str, Any]:
    """Resource-owner password grant via confidential ticketing-api client."""
    if not keycloak_configured():
        raise AuthLoginError("auth_unavailable", "Authentication is not configured.", 503)

    normalized = _normalize_email(email)
    if not normalized or "@" not in normalized:
        raise AuthLoginError("invalid_email", "Enter a valid email address.", 422)

    realm_base = _keycloak_realm_base()
    settings = get_settings()
    token_url = f"{realm_base}/protocol/openid-connect/token"
    client_secret = _api_client_secret()

    try:
        resp = _password_token_request(
            token_url,
            settings.keycloak_client_id,
            client_secret,
            normalized,
            password,
        )
    except httpx.HTTPError as exc:
        logger.error("Keycloak token request failed: %s", exc)
        raise AuthLoginError("auth_unavailable", "Sign-in service is temporarily unavailable.", 503) from exc

    if resp.status_code == 401:
        err, desc = _parse_token_error(resp)
        desc_lower = desc.lower()
        if err == "unauthorized_client" or "invalid client credentials" in desc_lower:
            logger.error("Keycloak client authentication failed: %s", desc or err)
            raise AuthLoginError(
                "auth_unavailable",
                "Sign-in service is misconfigured. Contact your administrator.",
                503,
            )
        if err == "invalid_grant" and "invalid user credentials" in desc_lower:
            raise AuthLoginError(
                "invalid_credentials",
                "Incorrect password. Try again or use Forgot password.",
                401,
            )
        logger.warning("Keycloak login unauthorized (%s): %s", err, desc)
        raise AuthLoginError(
            "invalid_credentials",
            "Incorrect password. Try again or use Forgot password.",
            401,
        )

    if not resp.is_success:
        err, desc = _parse_token_error(resp)
        desc_lower = desc.lower()
        if "not fully set up" in desc_lower:
            user = _find_keycloak_user(normalized)
            if user and (user.get("requiredActions") or []):
                raise AuthLoginError(
                    "account_setup_required",
                    "Your account setup is incomplete. Open the invite link from your email, "
                    "or use “Resend setup link” on the sign-in page.",
                    403,
                )
            if user:
                try:
                    admin = _keycloak_admin()
                    _ensure_keycloak_profile_ready(admin, user, normalized)
                    resp = _password_token_request(
                        token_url,
                        settings.keycloak_client_id,
                        client_secret,
                        normalized,
                        password,
                    )
                    if resp.is_success:
                        data = resp.json()
                        if data.get("access_token"):
                            return data
                except Exception as exc:
                    logger.warning("Keycloak profile auto-repair failed for %s: %s", normalized, exc)
            raise AuthLoginError(
                "account_setup_required",
                "Your account profile is incomplete. Use Forgot password or contact your administrator.",
                403,
            )
        if "account is disabled" in desc_lower:
            raise AuthLoginError(
                "account_setup_required",
                "Your account is disabled. Contact your administrator.",
                403,
            )
        if "user not found" in desc_lower or "invalid user" in desc_lower:
            raise AuthLoginError(
                "user_not_found",
                "No officer account exists for this email. Contact your administrator.",
                404,
            )
        logger.warning("Keycloak login failed (%s): %s", resp.status_code, desc)
        raise AuthLoginError(
            "login_failed",
            "Sign-in failed. Please try again or contact your administrator.",
            400,
        )

    data = resp.json()
    if not data.get("access_token"):
        raise AuthLoginError("login_failed", "Sign-in failed — no token received.", 502)
    return data


def _reset_token(email: str) -> str:
    settings = get_settings()
    secret = settings.ticketing_secret_key
    if not secret:
        raise AuthLoginError("auth_unavailable", "Password reset is not configured.", 503)
    now = int(time.time())
    return jwt.encode(
        {"sub": email, "purpose": RESET_PURPOSE, "iat": now, "exp": now + RESET_TTL_SECONDS},
        secret,
        algorithm="HS256",
    )


def _verify_reset_token(token: str) -> str:
    settings = get_settings()
    secret = settings.ticketing_secret_key
    if not secret:
        raise AuthLoginError("auth_unavailable", "Password reset is not configured.", 503)
    try:
        claims = jwt.decode(token, secret, algorithms=["HS256"])
    except JWTError as exc:
        raise AuthLoginError(
            "invalid_token",
            "This reset link is invalid or has expired. Request a new one from the sign-in page.",
            400,
        ) from exc
    if claims.get("purpose") != RESET_PURPOSE:
        raise AuthLoginError("invalid_token", "This reset link is invalid.", 400)
    email = _normalize_email(str(claims.get("sub") or ""))
    if not email or "@" not in email:
        raise AuthLoginError("invalid_token", "This reset link is invalid.", 400)
    return email


def request_password_reset(email: str, redirect_base: str) -> None:
    """Email a signed reset link via Messaging API (always succeeds from caller's view)."""
    if not keycloak_configured():
        raise AuthLoginError("auth_unavailable", "Authentication is not configured.", 503)

    normalized = _normalize_email(email)
    if not normalized or "@" not in normalized:
        raise AuthLoginError("invalid_email", "Enter a valid email address.", 422)

    base = _validate_redirect_base(redirect_base)
    user = _find_keycloak_user(normalized)
    if not user or not user.get("enabled", True):
        logger.info("Password reset requested for unknown/disabled user %s", normalized)
        return

    token = _reset_token(normalized)
    reset_url = f"{base}/login/reset-password?token={token}&email={normalized}"

    from ticketing.clients.messaging_api import send_email

    subject = "Reset your GRM Ticketing password"
    html = f"""
    <p>Hello,</p>
    <p>We received a request to reset the password for your GRM Ticketing officer account
    (<strong>{normalized}</strong>).</p>
    <p><a href="{reset_url}">Reset your password</a></p>
    <p>This link expires in one hour. If you did not request this, you can ignore this email.</p>
    <p style="color:#666;font-size:12px;">GRM Ticketing — ADB Grievance Redress Mechanism</p>
    """
    try:
        send_email(normalized, subject, html)
    except Exception as exc:
        logger.error("Password reset email failed for %s: %s", normalized, exc)
        raise AuthLoginError(
            "email_failed",
            "Could not send the reset email. Try again later or contact your administrator.",
            503,
        ) from exc


INVITE_SETUP_LINK_GENERIC = (
    "If an invited officer account exists for that email, we sent a new setup link. "
    "Check your inbox and spam folder. The link expires in 7 days."
)

_INVITE_RESEND_COOLDOWN_SEC = 120


def request_invite_setup_link(email: str, db) -> None:
    """
    Self-service: resend Keycloak execute-actions email for invited officers.
    Always appears to succeed from the caller's perspective when not eligible (no enumeration).
    """
    from datetime import datetime, timedelta, timezone

    from fastapi import HTTPException

    from ticketing.models.officer_onboarding import OfficerOnboarding
    from ticketing.services.officer_admin import (
        keycloak_configured,
        keycloak_resend_invite_email,
        officer_eligible_for_invite_resend,
    )

    if not keycloak_configured():
        raise AuthLoginError("auth_unavailable", "Authentication is not configured.", 503)

    normalized = _normalize_email(email)
    if not normalized or "@" not in normalized:
        raise AuthLoginError("invalid_email", "Enter a valid email address.", 422)

    if not officer_eligible_for_invite_resend(db, normalized):
        logger.info("Invite setup link requested for non-eligible email %s", normalized)
        return

    ob = db.get(OfficerOnboarding, normalized)
    if ob and ob.updated_at:
        age = datetime.now(timezone.utc) - ob.updated_at
        if age < timedelta(seconds=_INVITE_RESEND_COOLDOWN_SEC):
            logger.info("Invite setup link throttled for %s", normalized)
            return

    try:
        keycloak_resend_invite_email(normalized, db=db)
    except HTTPException as exc:
        if exc.status_code == 503:
            detail = exc.detail if isinstance(exc.detail, str) else "Could not send email."
            raise AuthLoginError("email_failed", detail, 503) from exc
        logger.warning("Invite setup link failed for %s: %s", normalized, exc.detail)
    except Exception as exc:
        logger.error("Invite setup link failed for %s: %s", normalized, exc)


def reset_password_with_token(token: str, new_password: str) -> str:
    """Reset password via signed token. Returns normalized officer email."""
    email = _verify_reset_token(token)
    if len(new_password) < 8:
        raise AuthLoginError("weak_password", "Password must be at least 8 characters.", 422)

    user = _find_keycloak_user(email)
    if not user:
        raise AuthLoginError("user_not_found", "No officer account exists for this email.", 404)

    admin = _keycloak_admin()
    admin.set_user_password(user["id"], new_password, temporary=False)
    _ensure_keycloak_profile_ready(admin, user, email)
    return email
