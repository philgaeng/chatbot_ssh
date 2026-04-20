"""
FastAPI dependency injection for GRM Ticketing.

Auth stubs:
  - verify_api_key: simple secret for chatbot → ticketing inbound calls
  - get_current_user: INTEGRATION POINT — replace stub with Cognito JWT
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generator

from fastapi import Depends, Header, HTTPException, status
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

    INTEGRATION POINT: consider rotating to a per-client key scheme in v2.
    """
    settings = get_settings()
    if not settings.ticketing_secret_key:
        # Dev-only shortcut: if no key is configured, skip check and warn
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


def get_current_user() -> CurrentUser:
    """
    INTEGRATION POINT: AWS Cognito JWT verification.

    Replace this stub with real JWT validation:

        from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
        from ticketing.auth.cognito import verify_cognito_token

        security = HTTPBearer()

        def get_current_user(
            credentials: HTTPAuthorizationCredentials = Depends(security),
        ) -> CurrentUser:
            claims = verify_cognito_token(credentials.credentials)
            return CurrentUser(
                user_id=claims["sub"],
                role_keys=claims.get("custom:grm_roles", "").split(","),
                organization_id=claims.get("custom:organization_id", ""),
                location_code=claims.get("custom:location_code"),
            )

    For proto: returns a mock super_admin with full access.
    """
    return CurrentUser(
        user_id="mock-super-admin",
        role_keys=["super_admin"],
        organization_id="DOR",
        location_code=None,
    )
