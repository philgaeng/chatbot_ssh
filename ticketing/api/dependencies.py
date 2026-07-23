"""
FastAPI dependency injection for GRM Ticketing.

Auth:
  - verify_api_key: simple secret for chatbot → ticketing inbound calls
  - get_current_user / get_authenticated_user (equivalent):
      • Resolve identity (Keycloak JWT, dev bypass, or internal x-api-key header)
      • Always load ticketing.admin_scopes for the user (country/project admin matrix)
      • Sync Keycloak onboarding status when user_id is an email
  - require_admin / require_super_admin / require_org_admin: use get_authenticated_user
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
    is_org_admin,
    is_project_admin,
    is_super_admin,
    load_admin_scopes,
    load_effective_role_keys,
    load_user_role_keys,
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
        # Fail-closed (HR-01): only the explicit dev bypass (APP_ENV=dev AUTH_MODE=bypass)
        # may run without a shared secret. Anywhere else, refuse to serve rather than
        # accept any API key.
        if settings.bypass_enabled:
            import warnings
            warnings.warn("TICKETING_SECRET_KEY not set — API key check disabled (dev bypass)", stacklevel=2)
            return x_api_key
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ticketing auth not configured (TICKETING_SECRET_KEY unset)",
        )
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
    # Track-derived SEAH access (DESIGN-cast-model §3.1): True when the officer is cast on a
    # SEAH-track workflow. Computed once per request in enrich_user; augments SEAH_ROLES.
    seah_track_member: bool = False

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

    def is_org_admin(self, track: Literal["standard", "seah"] | None = None) -> bool:
        return is_org_admin(self, track)

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


def _resolve_user_identity(
    credentials: HTTPAuthorizationCredentials | None,
    x_internal_user_id: str | None,
    x_internal_role: str | None,
    x_internal_organization_id: str | None,
    x_api_key: str | None,
) -> CurrentUser:
    """Resolve officer identity from JWT, dev bypass, or trusted internal headers."""
    settings = get_settings()

    if settings.bypass_enabled:
        # Dev bypass (APP_ENV=dev AUTH_MODE=bypass): resolve the mock super-admin, or
        # the roster officer injected by the Next proxy via x-internal-* headers.
        org = (x_internal_organization_id or "").strip() or "DOR"
        uid = x_internal_user_id or BYPASS_DEFAULT_OFFICER
        return CurrentUser(
            user_id=uid,
            role_keys=(x_internal_role or "super_admin").split(","),
            organization_id=org,
            keycloak_sub=uid,
        )

    if not settings.keycloak_issuer:
        # Fail-closed (HR-01): keycloak mode with no issuer must refuse to serve,
        # never authenticate everyone as super_admin. (Startup already blocks boot;
        # this is defense in depth.)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ticketing auth not configured (KEYCLOAK_ISSUER unset)",
        )

    # Prefer JWT when the browser sent one — stale demo bypass cookies must not
    # override Keycloak auth via x-internal-user-id injected by the Next proxy.
    if credentials:
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

    if x_internal_user_id and settings.ticketing_secret_key:
        if x_api_key == settings.ticketing_secret_key:
            # Least-privilege identity (HR-01): a header-injected caller gets NO roles
            # by default — no more silent super_admin. Callers that need capability
            # (the dev-bypass Next proxy) always send an explicit x-internal-role.
            role_keys = [r.strip() for r in (x_internal_role or "").split(",") if r.strip()]
            return CurrentUser(
                user_id=x_internal_user_id,
                role_keys=role_keys,
                organization_id="DOR",
                keycloak_sub=x_internal_user_id,
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="x-internal-user-id requires a valid x-api-key",
        )

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


def enrich_user(db: Session, user: CurrentUser) -> CurrentUser:
    user.admin_scopes = load_admin_scopes(db, user.user_id)
    if user.user_id and "@" in user.user_id:
        effective = load_effective_role_keys(db, user.user_id)
        if effective:
            # DB scopes + roster supersede stale JWT grm_roles claims.
            user.role_keys = effective
        elif not user.role_keys:
            user.role_keys = load_user_role_keys(db, user.user_id)
    # Frame-11 (officer lifecycle): a soft-deactivated officer keeps their history but
    # loses ALL GRM access — strip operational roles and admin scopes at the choke point
    # every authenticated request passes through.
    if user.user_id:
        from ticketing.services.officer_admin import officer_is_active

        if not officer_is_active(db, user.user_id):
            user.role_keys = []
            user.admin_scopes = []
    # Track-derived SEAH membership (DESIGN-cast-model §3.1) — computed after role_keys are
    # finalized (so a deactivated officer, now role-less, is not a track member).
    from ticketing.services.seah_visibility import user_is_seah_track_member

    user.seah_track_member = user_is_seah_track_member(db, user.role_keys)
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    x_internal_user_id: str | None = Header(None),
    x_internal_role: str | None = Header(None),
    x_internal_organization_id: str | None = Header(None),
    x_api_key: str | None = Header(None),
    db: Session = Depends(get_db),
) -> CurrentUser:
    """
    Authenticated officer with admin_scopes loaded from ticketing.admin_scopes.
    """
    user = _resolve_user_identity(
        credentials,
        x_internal_user_id,
        x_internal_role,
        x_internal_organization_id,
        x_api_key,
    )
    # The onboarding sync is a Keycloak admin operation. Skip it under the dev bypass
    # (AUTH_MODE=bypass / APP_ENV=dev has no Keycloak running) so bypass auth doesn't
    # 500 trying to reach a server that isn't there.
    if (
        not get_settings().bypass_enabled
        and user.user_id
        and "@" in user.user_id
    ):
        # H2-05: throttle the onboarding-status sync to once per TTL per officer. On a cache
        # hit we skip it entirely — no officer_onboarding read, no Keycloak round-trip, no
        # write — since the sync is idempotent and any status write invalidates the entry.
        from ticketing.services import auth_sync_cache

        if not auth_sync_cache.is_fresh(user.user_id):
            from ticketing.services.officer_admin import sync_officer_onboarding_status

            if sync_officer_onboarding_status(db, user.user_id):
                db.commit()
            auth_sync_cache.mark_synced(user.user_id)
    return enrich_user(db, user)


def get_authenticated_user(
    user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Alias for get_current_user — kept for explicit call sites and tests."""
    return user


def require_admin(current_user: CurrentUser = Depends(get_authenticated_user)) -> CurrentUser:
    """Transitional: any tier admin (super, scoped country/project, or legacy local_admin)."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_user


def require_admin_or_bypass(
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> CurrentUser:
    """Admin-gated under real auth; open to any authenticated identity in dev bypass.

    The officer roster (names / emails / jurisdictions) stays admin-only under Keycloak.
    In bypass mode (APP_ENV=dev + AUTH_MODE=bypass) it is a demo convenience: the officer
    switcher must be able to render the roster while acting as a *non-admin* officer,
    otherwise switching away from admin is a one-way door — the switcher can no longer load
    the list that would switch you back (D-65, 2026-07-16). `bypass_enabled` is dev-only
    (HR-01 pins it to APP_ENV=dev + AUTH_MODE=bypass), so this never widens access under
    real auth.
    """
    if get_settings().bypass_enabled:
        return current_user
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


def require_org_admin(
    track: Literal["standard", "seah"] | None = None,
):
    def _dep(current_user: CurrentUser = Depends(get_authenticated_user)) -> CurrentUser:
        if current_user.is_super_admin:
            return current_user
        if current_user.is_org_admin(track):
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
