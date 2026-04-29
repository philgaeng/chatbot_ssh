"""
Officer user management endpoints.

INTEGRATION POINT: full Cognito invite flow (create user → Cognito invite → set password)
is deferred to post-proto. For proto, role assignments are managed via seed data.
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ticketing.api.dependencies import CurrentUser, get_current_user, get_db
from ticketing.api.schemas.user import (
    NotificationBadgeResponse,
    RoleResponse,
    UserRoleCreate,
    UserRoleResponse,
)
from ticketing.models.officer_scope import OfficerScope
from ticketing.models.ticket import TicketEvent
from ticketing.models.user import Role, UserRole

router = APIRouter()


# ── Roles ─────────────────────────────────────────────────────────────────────

@router.get("/roles", response_model=list[RoleResponse], summary="List all GRM roles")
def list_roles(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
) -> list[Role]:
    return db.execute(select(Role).order_by(Role.role_key)).scalars().all()


# ── User roles ─────────────────────────────────────────────────────────────────

@router.get(
    "/users/{user_id}/roles",
    response_model=list[UserRoleResponse],
    summary="List role assignments for an officer",
)
def get_user_roles(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[UserRole]:
    # Officers can only see their own roles unless admin
    if user_id != current_user.user_id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Access denied")
    return db.execute(
        select(UserRole).where(UserRole.user_id == user_id)
    ).scalars().all()


@router.post(
    "/users/{user_id}/roles",
    response_model=UserRoleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign a role to an officer (admin only)",
)
def assign_role(
    user_id: str,
    payload: UserRoleCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> UserRole:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    role = db.get(Role, payload.role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    user_role = UserRole(
        user_id=user_id,
        role_id=payload.role_id,
        organization_id=payload.organization_id,
        location_code=payload.location_code,
    )
    db.add(user_role)
    db.commit()
    db.refresh(user_role)
    return user_role


@router.delete(
    "/users/{user_id}/roles/{user_role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a role assignment (admin only)",
)
def remove_role(
    user_id: str,
    user_role_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    user_role = db.get(UserRole, user_role_id)
    if not user_role or user_role.user_id != user_id:
        raise HTTPException(status_code=404, detail="Role assignment not found")
    db.delete(user_role)
    db.commit()


# ── Officers list (for assign dropdown) ──────────────────────────────────────

class OfficerBrief(BaseModel):
    user_id: str
    role_keys: list[str]
    organization_id: str | None = None
    location_code: str | None = None


@router.get(
    "/users/officers",
    response_model=list[OfficerBrief],
    summary="List all officers with roles (for assign dropdown)",
)
def list_officers(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
) -> list[OfficerBrief]:
    """
    Returns distinct user_ids from ticketing.user_roles with their role keys.
    Used to populate the assign-to-officer dropdown in the ticket detail UI.
    """
    rows = db.execute(
        select(UserRole.user_id, Role.role_key, UserRole.organization_id, UserRole.location_code)
        .join(Role, Role.role_id == UserRole.role_id)
        .order_by(UserRole.user_id, Role.role_key)
    ).all()

    # Group by user_id
    by_user: dict[str, OfficerBrief] = {}
    for user_id, role_key, org_id, loc_code in rows:
        if user_id not in by_user:
            by_user[user_id] = OfficerBrief(
                user_id=user_id,
                role_keys=[role_key],
                organization_id=org_id,
                location_code=loc_code,
            )
        else:
            by_user[user_id].role_keys.append(role_key)

    return list(by_user.values())


# ── Officer jurisdiction scopes ───────────────────────────────────────────────

class ScopeCreate(BaseModel):
    role_key: str
    organization_id: str
    location_code: Optional[str] = None
    # Use project_id (FK to ticketing.projects); project_code kept for legacy callers
    project_id: Optional[str] = None
    project_code: Optional[str] = None          # deprecated — ignored if project_id given
    # When set: scope is restricted to this specific civil-works package
    package_id: Optional[str] = None
    includes_children: bool = False             # True: scope cascades to child locations


class ScopeResponse(BaseModel):
    scope_id: str
    user_id: str
    role_key: str
    organization_id: str
    location_code: Optional[str]
    project_id: Optional[str]
    project_code: Optional[str]
    package_id: Optional[str]
    includes_children: bool
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get(
    "/users/{user_id}/scopes",
    response_model=list[ScopeResponse],
    summary="List jurisdiction scopes for an officer",
)
def get_user_scopes(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[OfficerScope]:
    # Officers can view their own scopes; admins can view any
    if user_id != current_user.user_id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Access denied")
    return db.execute(
        select(OfficerScope)
        .where(OfficerScope.user_id == user_id)
        .order_by(OfficerScope.created_at)
    ).scalars().all()


@router.post(
    "/users/{user_id}/scopes",
    response_model=ScopeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a jurisdiction scope to an officer (local_admin or super_admin only)",
)
def add_user_scope(
    user_id: str,
    payload: ScopeCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> OfficerScope:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    # Validate project_id if supplied; backfill project_code from short_code so that
    # _scope_candidates (which queries by project_code) keeps working for new scopes.
    resolved_project_code: Optional[str] = payload.project_code
    if payload.project_id:
        from ticketing.models.project import Project
        project = db.get(Project, payload.project_id)
        if not project:
            raise HTTPException(status_code=422, detail=f"Project '{payload.project_id}' not found")
        resolved_project_code = project.short_code  # canonical key used by routing engine

    # Validate package_id if supplied
    if payload.package_id:
        from ticketing.models.package import Package
        if not db.get(Package, payload.package_id):
            raise HTTPException(status_code=422, detail=f"Package '{payload.package_id}' not found")

    # Prevent duplicate entries for the same (user, role, org, location, project, package)
    existing = db.execute(
        select(OfficerScope).where(
            OfficerScope.user_id == user_id,
            OfficerScope.role_key == payload.role_key,
            OfficerScope.organization_id == payload.organization_id,
            OfficerScope.location_code == payload.location_code,
            OfficerScope.project_id == payload.project_id,
            OfficerScope.package_id == payload.package_id,
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Scope already exists for this officer / role / jurisdiction combination",
        )

    scope = OfficerScope(
        user_id=user_id,
        role_key=payload.role_key,
        organization_id=payload.organization_id,
        location_code=payload.location_code,
        project_id=payload.project_id,
        # Always populate project_code (routing engine queries by this field).
        # When project_id provided: use project.short_code (resolved above).
        # When only project_code provided (legacy callers): use that directly.
        project_code=resolved_project_code,
        package_id=payload.package_id,
        includes_children=payload.includes_children,
    )
    db.add(scope)
    db.commit()
    db.refresh(scope)
    return scope


@router.delete(
    "/users/{user_id}/scopes/{scope_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a jurisdiction scope from an officer (admin only)",
)
def remove_user_scope(
    user_id: str,
    scope_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    scope = db.get(OfficerScope, scope_id)
    if not scope or scope.user_id != user_id:
        raise HTTPException(status_code=404, detail="Scope not found")
    db.delete(scope)
    db.commit()


# ── User language preferences ─────────────────────────────────────────────────

class UserPreferencesResponse(BaseModel):
    user_id: str
    preferred_language: Optional[str]       # officer-level override (null = use org default)
    org_default_language: str               # from ticketing.organizations.default_language
    effective_language: str                 # resolved: preferred_language ?? org_default ?? 'en'


class UserPreferencesPatch(BaseModel):
    preferred_language: Optional[str] = None   # 'en', 'ne', or null to reset to org default


@router.get(
    "/users/me/preferences",
    response_model=UserPreferencesResponse,
    summary="Get current officer's language preferences",
    description=(
        "Returns the officer's effective language, their personal override (if any), "
        "and their organisation's default. "
        "effective_language drives inline translation chip visibility in the UI."
    ),
)
def get_my_preferences(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> UserPreferencesResponse:
    from ticketing.models.organization import Organization

    # Look up any personal override on the first user_role row for this user
    user_role = db.execute(
        select(UserRole).where(UserRole.user_id == current_user.user_id).limit(1)
    ).scalar_one_or_none()
    preferred_language: Optional[str] = user_role.preferred_language if user_role else None

    # Fetch org default
    org = db.get(Organization, current_user.organization_id)
    org_default = org.default_language if org else "en"

    # Resolve: personal > org > hard fallback
    effective = preferred_language or org_default or "en"

    return UserPreferencesResponse(
        user_id=current_user.user_id,
        preferred_language=preferred_language,
        org_default_language=org_default,
        effective_language=effective,
    )


@router.patch(
    "/users/me/preferences",
    response_model=UserPreferencesResponse,
    summary="Update current officer's language preference",
    description=(
        "Set preferred_language to 'en' or 'ne' to override the org default. "
        "Set to null to reset to the org default."
    ),
)
def patch_my_preferences(
    body: UserPreferencesPatch,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> UserPreferencesResponse:
    from ticketing.models.organization import Organization

    if body.preferred_language not in (None, "en", "ne"):
        from fastapi import HTTPException
        raise HTTPException(
            status_code=422,
            detail="preferred_language must be 'en', 'ne', or null (reset to org default)",
        )

    # Update preferred_language on ALL user_role rows for this user (they share a preference)
    rows = db.execute(
        select(UserRole).where(UserRole.user_id == current_user.user_id)
    ).scalars().all()
    for row in rows:
        row.preferred_language = body.preferred_language
    db.commit()

    org = db.get(Organization, current_user.organization_id)
    org_default = org.default_language if org else "en"
    effective = body.preferred_language or org_default or "en"

    return UserPreferencesResponse(
        user_id=current_user.user_id,
        preferred_language=body.preferred_language,
        org_default_language=org_default,
        effective_language=effective,
    )


# ── Officer invite (Keycloak Admin API) ──────────────────────────────────────

class OfficerInviteRequest(BaseModel):
    email: str
    role_key: str
    organization_id: str
    temp_password: Optional[str] = None


class OfficerInviteResponse(BaseModel):
    ok: bool
    email: str
    message: str


@router.post(
    "/users/invite",
    response_model=OfficerInviteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Invite a new officer (admin only) — creates user in Keycloak",
)
def invite_officer(
    body: OfficerInviteRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> OfficerInviteResponse:
    """
    Creates the user in Keycloak with a temporary password and UPDATE_PASSWORD
    required action. Keycloak sends the verification email if SMTP is configured.
    For proto, the temp password is set to the value in the request (or a default).
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    from ticketing.config.settings import get_settings
    settings = get_settings()
    if not settings.keycloak_admin_url:
        raise HTTPException(
            status_code=503,
            detail="Keycloak not configured — set KEYCLOAK_ADMIN_URL to enable officer invite",
        )

    try:
        from keycloak import KeycloakAdmin, KeycloakOpenIDConnection
        from keycloak.exceptions import KeycloakPostError

        conn = KeycloakOpenIDConnection(
            server_url=settings.keycloak_admin_url.rstrip("/") + "/",
            username="admin",
            password=settings.keycloak_admin_password,
            realm_name="grm",
            user_realm_name="master",
            verify=True,
        )
        admin = KeycloakAdmin(connection=conn)
        admin.create_user({
            "username": body.email,
            "email": body.email,
            "enabled": True,
            "attributes": {
                "grm_roles": body.role_key,
                "organization_id": body.organization_id,
            },
            "credentials": [{
                "type": "password",
                "value": body.temp_password or "ChangeMe123!",
                "temporary": True,
            }],
            "requiredActions": ["UPDATE_PASSWORD"],
        })
    except Exception as exc:
        err = str(exc)
        if "409" in err or "already exists" in err.lower():
            raise HTTPException(status_code=409, detail=f"User {body.email!r} already exists in Keycloak")
        raise HTTPException(status_code=500, detail=f"Keycloak error: {err}")

    return OfficerInviteResponse(
        ok=True,
        email=body.email,
        message="Officer created in Keycloak — they will receive a setup email if SMTP is configured.",
    )


# ── Notification badge ────────────────────────────────────────────────────────

@router.get(
    "/users/me/badge",
    response_model=NotificationBadgeResponse,
    summary="Get unread notification count for the current officer",
)
def get_badge(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> NotificationBadgeResponse:
    from sqlalchemy import func
    count = db.execute(
        select(func.count(TicketEvent.event_id)).where(
            TicketEvent.assigned_to_user_id == current_user.user_id,
            TicketEvent.seen.is_(False),
        )
    ).scalar_one()
    return NotificationBadgeResponse(unseen_count=count)
