"""Public auth endpoints (login + password reset). No JWT required."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ticketing.api.dependencies import get_db
from ticketing.services.auth_login import (
    INVITE_SETUP_LINK_GENERIC,
    AuthLoginError,
    login_with_password,
    request_invite_setup_link,
    request_password_reset,
    reset_password_with_token,
)

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


def _http_error(exc: AuthLoginError):
    from fastapi import HTTPException

    return HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": exc.message},
    )


@router.post("/auth/login", response_model=LoginResponse, summary="Sign in with email and password")
def auth_login(body: LoginRequest) -> LoginResponse:
    try:
        tokens = login_with_password(body.email, body.password)
    except AuthLoginError as exc:
        raise _http_error(exc) from exc
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
def auth_reset_password(body: ResetPasswordRequest) -> MessageResponse:
    try:
        reset_password_with_token(body.token, body.password)
    except AuthLoginError as exc:
        raise _http_error(exc) from exc
    return MessageResponse(message="Your password has been updated. You can sign in now.")
