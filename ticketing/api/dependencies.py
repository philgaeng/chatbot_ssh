"""
FastAPI dependency injection for GRM Ticketing.

Auth:
  - verify_api_key: simple secret for chatbot → ticketing inbound calls
  - get_current_user:
      • KEYCLOAK_ISSUER not set → dev bypass (returns mock-super-admin)
      • x-internal-user-id header present → trust header (internal service calls)
      • Otherwise → validate Bearer JWT against Keycloak JWKS
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generator

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from ticketing.config.settings import get_settings
from ticketing.models.base import SessionLocal
from ticketing.models.user import SEAH_ROLES


# ── Database session ──────────────────────────────────────────────────────────

def get_db() -> Generator[Session, None, None]:
    """Yields a SQLAlchemy session; closes on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── API key (inbound from chatbot/backend) ────────────────────────────────────

def verify_api_key(x_api_key: str = Header(...)) -> str:
    """
    Validates the API key sent by the chatbot backend when creating tickets.
    Set TICKETING_SECRET_KEY in env.local.
    """
    settings = get_settings()
    if not settings.ticketing_secret_key:
        import warnings
        warnings.warn("TICKETING_SECRET_KEY not set — API key check disabled (dev mode)", stacklevel=2)
        return x_api_key
    if x_api_key != settings.ticketing_secret_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return x_api_key


# ── Officer identity ──────────────────────────────────────────────────────────

@dataclass
class CurrentUser:
    user_id: str
    role_keys: list[str] = field(default_factory=list)
    organization_id: str = ""
    location_code: str | None = None

    @property
    def is_seah_officer(self) -> bool:
        return bool(set(self.role_keys) & SEAH_ROLES)

    @property
    def is_admin(self) -> bool:
        return any(r in ("super_admin", "local_admin") for r in self.role_keys)

    @property
    def can_see_seah(self) -> bool:
        """super_admin and adb_hq_exec can see both queues."""
        return self.is_seah_officer or any(
            r in ("super_admin", "adb_hq_exec") for r in self.role_keys
        )


_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    x_internal_user_id: str | None = Header(None),
    x_internal_role: str | None = Header(None),
) -> CurrentUser:
    """
    Resolve the calling officer:

    1. Dev bypass — KEYCLOAK_ISSUER is empty (no Keycloak running locally):
       returns mock-super-admin so development works without auth infrastructure.

    2. Internal service header — x-internal-user-id present (chatbot → ticketing
       or Celery → ticketing internal calls): trusts the header, skips JWT.

    3. Normal path — validates the Bearer JWT against Keycloak JWKS.
    """
    settings = get_settings()

    # Dev bypass: no Keycloak configured
    if not settings.keycloak_issuer:
        return CurrentUser(
            user_id=x_internal_user_id or "mock-super-admin",
            role_keys=(x_internal_role or "super_admin").split(","),
            organization_id="DOR",
        )

    # Internal service-to-service call (trusted header)
    if x_internal_user_id:
        return CurrentUser(
            user_id=x_internal_user_id,
            role_keys=(x_internal_role or "super_admin").split(","),
            organization_id="DOR",
        )

    # Normal path: validate Keycloak JWT
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    from ticketing.auth.keycloak_jwt import verify_keycloak_token
    try:
        claims = verify_keycloak_token(credentials.credentials)
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {exc}")

    return CurrentUser(
        user_id=claims["sub"],
        role_keys=claims.get("custom:grm_roles", "").split(","),
        organization_id=claims.get("custom:organization_id", ""),
        location_code=claims.get("custom:location_code"),
    )
