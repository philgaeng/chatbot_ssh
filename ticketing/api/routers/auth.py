# SPDX-License-Identifier: Apache-2.0

"""Public auth endpoints (login + password reset). No JWT required."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ticketing.api.dependencies import get_db
from ticketing.services.auth_login import (
    INVITE_SETUP_LINK_GENERIC,
    AuthLoginError,
    login_with_password,
    logout_with_refresh_token,
    request_invite_setup_link,
    request_password_reset,
    reset_password_with_token,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=1, max_length=256)


class LoginResponse(BaseModel):
    access_token: str
    id_token: str | None = None
    refresh_token: str | None = None
    expires_in: int
    token_type: str = "Bearer"


class LogoutRequest(BaseModel):
    refresh_token: str = Field(..., min_length=10, max_length=8192)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    redirect_base: str = Field(..., min_length=8, max_length=256)


class RequestInviteLinkRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=10)
    password: str = Field(..., min_length=8, max_length=256)


class MessageResponse(BaseModel):
    message: str


class LogoutResponse(BaseModel):
    """⚠ `revoked` is the whole point of this model, and it is NOT the HTTP status.

    The status stays 200 even when the revoke fails, because a sign-out that returns an error
    invites a UI that keeps the user signed in. But the client still has to *know*, so it can
    fall back to the front-channel Keycloak logout — which is the guaranteed mechanism. Putting
    that in the body keeps both properties: never fail the sign-out, never hide the failure.
    """

    message: str
    revoked: bool


def _http_error(exc: AuthLoginError):
    from fastapi import HTTPException

    return HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": exc.message},
    )


@router.post("/auth/login", response_model=LoginResponse, summary="Sign in with email and password")
def auth_login(body: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    try:
        tokens = login_with_password(body.email, body.password)
    except AuthLoginError as exc:
        raise _http_error(exc) from exc
    from ticketing.services.officer_admin import sync_officer_onboarding_status

    if sync_officer_onboarding_status(db, body.email):
        db.commit()
    return LoginResponse(
        access_token=tokens["access_token"],
        id_token=tokens.get("id_token"),
        refresh_token=tokens.get("refresh_token"),
        expires_in=int(tokens.get("expires_in") or 3600),
        token_type=tokens.get("token_type") or "Bearer",
    )


@router.post(
    "/auth/forgot-password",
    response_model=MessageResponse,
    summary="Email a password reset link",
)
def auth_forgot_password(body: ForgotPasswordRequest) -> MessageResponse:
    try:
        request_password_reset(body.email, body.redirect_base)
    except AuthLoginError as exc:
        raise _http_error(exc) from exc
    return MessageResponse(
        message="If an account exists for that email, we sent password reset instructions.",
    )


@router.post(
    "/auth/request-invite-link",
    response_model=MessageResponse,
    summary="Self-service: request a new officer setup email (expired invite link)",
)
def auth_request_invite_link(
    body: RequestInviteLinkRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    try:
        request_invite_setup_link(body.email, db)
        db.commit()
    except AuthLoginError as exc:
        raise _http_error(exc) from exc
    return MessageResponse(message=INVITE_SETUP_LINK_GENERIC)


@router.post(
    "/auth/reset-password",
    response_model=MessageResponse,
    summary="Set a new password using a reset token",
)
def auth_reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)) -> MessageResponse:
    try:
        email = reset_password_with_token(body.token, body.password)
    except AuthLoginError as exc:
        raise _http_error(exc) from exc
    from ticketing.services.officer_admin import sync_officer_onboarding_status

    if sync_officer_onboarding_status(db, email):
        db.commit()
    return MessageResponse(message="Your password has been updated. You can sign in now.")


@router.post(
    "/auth/logout",
    response_model=LogoutResponse,
    summary="Revoke a refresh token issued to the confidential API client",
)
def auth_logout(body: LogoutRequest) -> LogoutResponse:
    """End the Keycloak session for a password-login token.

    ⚠ **Deliberately not JWT-gated.** The refresh token *is* the credential, and the access token is
    routinely gone by the time a user signs out — requiring a valid one would make this fail in the
    stale-session case that is the only case it is needed for.

    ⚠ **Always answers 200.** A sign-out that reports failure invites a UI that keeps the user signed
    in, which is the wrong direction to fail: the client clears its storage regardless, so a server
    error must not turn "revoke failed" into "still logged in here". The failure is logged and shows
    up as a `LOGOUT_ERROR` in the realm event log, which is where it belongs.
    """
    try:
        logout_with_refresh_token(body.refresh_token)
    except AuthLoginError as exc:
        logger.warning("auth_logout: revoke did not complete (%s)", exc.code)
        return LogoutResponse(message="Signed out.", revoked=False)
    return LogoutResponse(message="Signed out.", revoked=True)
