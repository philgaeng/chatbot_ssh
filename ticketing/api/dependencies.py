"""
FastAPI dependency injection for GRM Ticketing.

Auth:
  - verify_api_key: simple secret for chatbot → ticketing inbound calls
  - get_current_user:
      • KEYCLOAK_ISSUER not set → dev bypass (mock-super-admin unless
        x-internal-user-id; optional x-internal-organization-id)
      • x-internal-user-id header present → trust header (internal service calls)
      • Otherwise → validate Bearer JWT against Keycloak JWKS
  - get_authenticated_user: identity + admin_scopes from DB
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generator, Literal

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from ticketing.config.settings import get_settings
from ticketing.constants.demo_officers import BYPASS_DEFAULT_OFFICER, LEGACY_OFFICER_ID_MAP
from ticketing.models.base import SessionLocal
from ticketing.models.user import SEAH_ROLES
from ticketing.services.admin_access import (
    AdminScopeRow,
    SettingsAction,
    admin_workflow_tracks,
    can_access_platform_settings,
    can_create_operational_role,
    can_manage_structure,
    can_see_seah_extended,
    can_view_archived,
    is_any_admin,
    is_country_admin,
    is_project_admin,
    is_super_admin,
    load_admin_scopes,
    require_settings_write,
    require_track_for_mutation,
)


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
    keycloak_sub: str | None = None
    admin_scopes: list[AdminScopeRow] = field(default_factory=list)

    def matches_assignee(self, assignee_id: str | None) -> bool:
        """True when assignee_id is this officer (email, Keycloak sub, or legacy mock id)."""
        if not assignee_id:
            return False

        def _same_officer(a: str, b: str) -> bool:
            if a == b:
                return True
            if "@" in a and "@" in b and a.lower() == b.lower():
                return True
            return False

        assignee_aliases = {assignee_id.strip()}
        mapped = LEGACY_OFFICER_ID_MAP.get(assignee_id)
        if mapped:
            assignee_aliases.add(mapped)
        for legacy, canonical in LEGACY_OFFICER_ID_MAP.items():
            if canonical == assignee_id or canonical == mapped:
                assignee_aliases.add(legacy)

        officer_ids = {self.user_id}
        if self.keycloak_sub:
            officer_ids.add(self.keycloak_sub)

        for aid in assignee_aliases:
            for oid in officer_ids:
                if _same_officer(aid, oid):
                    return True
        return False

    @property
    def is_seah_officer(self) -> bool:
        return bool(set(self.role_keys) & SEAH_ROLES)

    @property
    def is_admin(self) -> bool:
        return is_any_admin(self)

    @property
    def is_super_admin(self) -> bool:
        return is_super_admin(self)

    def is_country_admin(self, track: Literal["standard", "seah"] | None = None) -> bool:
        return is_country_admin(self, track)

    def is_project_admin(
        self,
        project_id: str | None = None,
        track: Literal["standard", "seah"] | None = None,
    ) -> bool:
        return is_project_admin(self, project_id, track)

    @property
    def admin_workflow_tracks(self) -> set[str]:
        return admin_workflow_tracks(self)

    @property
    def can_access_platform_settings(self) -> bool:
        return can_access_platform_settings(self)

    @property
    def can_manage_structure(self) -> bool:
        return can_manage_structure(self)

    @property
    def can_see_seah(self) -> bool:
        return can_see_seah_extended(self)

    @property
    def can_view_archived(self) -> bool:
        return can_view_archived(self)


_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    x_internal_user_id: str | None = Header(None),
    x_internal_role: str | None = Header(None),
    x_internal_organization_id: str | None = Header(None),
    x_api_key: str | None = Header(None),
) -> CurrentUser:
    """
    Resolve the calling officer identity (no DB).
    """
    settings = get_settings()

    if not settings.keycloak_issuer:
        org = (x_internal_organization_id or "").strip() or "DOR"
        uid = x_internal_user_id or BYPASS_DEFAULT_OFFICER
        return CurrentUser(
            user_id=uid,
            role_keys=(x_internal_role or "super_admin").split(","),
            organization_id=org,
            keycloak_sub=uid,
        )

    if x_internal_user_id and settings.ticketing_secret_key:
        if x_api_key == settings.ticketing_secret_key:
            return CurrentUser(
                user_id=x_internal_user_id,
                role_keys=(x_internal_role or "super_admin").split(","),
                organization_id="DOR",
                keycloak_sub=x_internal_user_id,
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="x-internal-user-id requires a valid x-api-key",
        )

    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    from ticketing.auth.keycloak_jwt import user_id_from_keycloak_claims, verify_keycloak_token
    try:
        claims = verify_keycloak_token(credentials.credentials)
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {exc}")

    user_id = user_id_from_keycloak_claims(claims)
    role_raw = claims.get("custom:grm_roles", "")
    role_keys = [r.strip() for r in role_raw.split(",") if r.strip()]
    sub = claims.get("sub")
    return CurrentUser(
        user_id=user_id,
        role_keys=role_keys,
        organization_id=claims.get("custom:organization_id", ""),
        location_code=claims.get("custom:location_code"),
        keycloak_sub=sub if isinstance(sub, str) else None,
    )


def enrich_user(db: Session, user: CurrentUser) -> CurrentUser:
    user.admin_scopes = load_admin_scopes(db, user.user_id)
    return user


def get_authenticated_user(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Identity + admin_scopes loaded from ticketing.admin_scopes."""
    if user.user_id and "@" in user.user_id:
        from ticketing.services.officer_admin import sync_officer_onboarding_status

        if sync_officer_onboarding_status(db, user.user_id):
            db.commit()
    return enrich_user(db, user)


def require_admin(current_user: CurrentUser = Depends(get_authenticated_user)) -> CurrentUser:
    """Transitional: any tier admin (super, scoped country/project, or legacy local_admin)."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_user


def require_super_admin(current_user: CurrentUser = Depends(get_authenticated_user)) -> CurrentUser:
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin role required",
        )
    return current_user


def require_country_admin(
    track: Literal["standard", "seah"] | None = None,
):
    def _dep(current_user: CurrentUser = Depends(get_authenticated_user)) -> CurrentUser:
        if current_user.is_super_admin:
            return current_user
        if current_user.is_country_admin(track):
            return current_user
        detail = "Country admin required"
        if track:
            detail = f"Country admin required (track={track})"
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

    return _dep


def require_settings_write_dep(action: SettingsAction, track: str | None = None):
    def _dep(current_user: CurrentUser = Depends(get_authenticated_user)) -> CurrentUser:
        require_settings_write(current_user, action, track=track)
        return current_user

    return _dep
