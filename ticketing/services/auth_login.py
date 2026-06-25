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
