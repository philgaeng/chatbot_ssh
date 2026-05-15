"""
Officer user management endpoints.

INTEGRATION POINT: full Cognito invite flow (create user → Cognito invite → set password)
is deferred to post-proto. For proto, role assignments are managed via seed data.
"""
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ticketing.api.dependencies import CurrentUser, get_current_user, get_db, require_admin
from ticketing.api.schemas.user import (
    NotificationBadgeResponse,
    NotificationItem,
    NotificationsResponse,
    RoleResponse,
    RoleUpdate,
    UserRoleCreate,
    UserRoleResponse,
)
from ticketing.models.officer_scope import OfficerScope
from ticketing.models.officer_onboarding import OfficerOnboarding
from ticketing.models.ticket import Ticket, TicketEvent
from ticketing.models.user import Role, UserRole

router = APIRouter()


def _display_name_from_user_id(user_id: str) -> str:
    """Derive a short label — ticketing stores no PII; IdPs use email or opaque sub."""
    if "@" in user_id:
        local = user_id.split("@", 1)[0].replace(".", " ").replace("_", " ").strip()
        return local.title() if local else user_id
    if user_id.startswith("mock-"):
        return user_id[5:].replace("-", " ").title()
    if len(user_id) >= 32 and user_id.count("-") >= 4:
        return f"{user_id[:8]}…"
    return user_id


def _email_hint(user_id: str) -> str | None:
    return user_id if "@" in user_id else None


# ── Roles ─────────────────────────────────────────────────────────────────────

@router.get("/roles", response_model=list[RoleResponse], summary="List all GRM roles")
def list_roles(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
) -> list[Role]:
    return db.execute(select(Role).order_by(Role.role_key)).scalars().all()


@router.patch(
    "/roles/{role_id}",
    response_model=RoleResponse,
    summary="Update role catalog fields (admin)",
)
def update_role(
    role_id: str,
    body: RoleUpdate,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
) -> Role:
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if body.display_name is not None:
        role.display_name = body.display_name.strip()
    if body.description is not None:
        role.description = body.description.strip() or None
    if body.workflow_scope is not None:
        v = body.workflow_scope.strip()
        if v and v not in ("Standard", "SEAH", "Both"):
            raise HTTPException(
                status_code=422,
                detail="workflow_scope must be Standard, SEAH, Both, or empty",
            )
        role.workflow_scope = v or None
    role.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(role)
    return role


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
    from ticketing.services.officer_admin import log_admin_audit

    log_admin_audit(
        db,
        actor_user_id=current_user.user_id,
        action="officer.role.assign",
        target_user_id=user_id,
        payload={"role_id": str(payload.role_id), "organization_id": payload.organization_id},
    )
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
    from ticketing.services.officer_admin import log_admin_audit

    log_admin_audit(
        db,
        actor_user_id=current_user.user_id,
        action="officer.role.remove",
        target_user_id=user_id,
        payload={"user_role_id": user_role_id, "role_id": str(user_role.role_id)},
    )
    db.delete(user_role)
    db.commit()


# ── Officers list (for assign dropdown) ──────────────────────────────────────

class OfficerBrief(BaseModel):
    user_id: str
    role_keys: list[str]
    organization_id: str | None = None
    location_code: str | None = None


class OfficerRosterEntry(BaseModel):
    """One officer identity with all role rows aggregated from ticketing.user_roles."""

    user_id: str
    display_name: str
    email: str | None = None
    role_keys: list[str]
    organization_ids: list[str]
    location_codes: list[str]
    project_codes: list[str] = []
    package_ids: list[str] = []
    onboarding_status: str = "active"  # invited | active


@router.get(
    "/users/roster",
    response_model=list[OfficerRosterEntry],
    summary="List officers for Settings UI (admin) — from ticketing.user_roles",
)
def list_officer_roster(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
) -> list[OfficerRosterEntry]:
    """
    Admin roster: distinct user_ids from user_roles with merged roles and org/locations.
    No Keycloak call — identities are opaque user_id strings (email or sub).
    """
    rows = db.execute(
        select(UserRole.user_id, Role.role_key, UserRole.organization_id, UserRole.location_code)
        .join(Role, Role.role_id == UserRole.role_id)
        .order_by(UserRole.user_id, Role.role_key)
    ).all()

    order: list[str] = []
    role_keys_by: dict[str, list[str]] = {}
    seen_key: dict[str, set[str]] = defaultdict(set)
    orgs_by: dict[str, set[str]] = defaultdict(set)
    locs_by: dict[str, set[str]] = defaultdict(set)

    for uid, rk, org_id, loc in rows:
        if uid not in role_keys_by:
            role_keys_by[uid] = []
            order.append(uid)
        if rk not in seen_key[uid]:
            seen_key[uid].add(rk)
            role_keys_by[uid].append(rk)
        orgs_by[uid].add(org_id)
        if loc:
            locs_by[uid].add(loc)

    onboard_map: dict[str, str] = {}
    if order:
        ob_rows = db.execute(
            select(OfficerOnboarding).where(OfficerOnboarding.user_id.in_(order))
        ).scalars().all()
        onboard_map = {o.user_id: o.status for o in ob_rows}

    proj_by: dict[str, set[str]] = defaultdict(set)
    pkg_by: dict[str, set[str]] = defaultdict(set)
    if order:
        scope_rows = db.execute(
            select(
                OfficerScope.user_id,
                OfficerScope.project_code,
                OfficerScope.package_id,
            ).where(OfficerScope.user_id.in_(order))
        ).all()
        for uid, pcode, pkg_id in scope_rows:
            if pcode:
                proj_by[uid].add(pcode)
            if pkg_id:
                pkg_by[uid].add(pkg_id)

    return [
        OfficerRosterEntry(
            user_id=uid,
            display_name=_display_name_from_user_id(uid),
            email=_email_hint(uid),
            role_keys=role_keys_by[uid],
            organization_ids=sorted(orgs_by[uid]),
            location_codes=sorted(locs_by[uid]),
            project_codes=sorted(proj_by.get(uid, set())),
            package_ids=sorted(pkg_by.get(uid, set())),
            onboarding_status=onboard_map.get(uid, "active"),
        )
        for uid in order
    ]


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
        from ticketing.models.package import ProjectPackage
        if not db.get(ProjectPackage, payload.package_id):
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
    from ticketing.services.officer_admin import log_admin_audit

    log_admin_audit(
        db,
        actor_user_id=current_user.user_id,
        action="officer.scope.add",
        target_user_id=user_id,
        payload={
            "scope_id": str(scope.scope_id),
            "role_key": payload.role_key,
            "organization_id": payload.organization_id,
            "project_id": payload.project_id,
            "package_id": payload.package_id,
            "location_code": payload.location_code,
        },
    )
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
    from ticketing.services.officer_admin import log_admin_audit

    log_admin_audit(
        db,
        actor_user_id=current_user.user_id,
        action="officer.scope.remove",
        target_user_id=user_id,
        payload={"scope_id": scope_id, "role_key": scope.role_key},
    )
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


# ── Officer invite / update / delete ───────────────────────────────────────────

class OfficerInviteRequest(BaseModel):
    email: str
    role_key: str
    organization_id: str
    location_code: Optional[str] = None
    project_id: Optional[str] = None
    project_code: Optional[str] = None
    package_id: Optional[str] = None
    includes_children: bool = False
    temp_password: Optional[str] = None


class OfficerInviteResponse(BaseModel):
    ok: bool
    email: str
    message: str


class OfficerUpdateRequest(BaseModel):
    """Sync Keycloak claims from roster; jurisdiction rows managed via scope APIs."""
    role_keys: list[str]
    organization_id: str
    location_code: Optional[str] = None
    sync_keycloak: bool = True


class OfficerUpdateResponse(BaseModel):
    ok: bool
    user_id: str


@router.post(
    "/users/invite",
    response_model=OfficerInviteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Invite officer — Keycloak (if configured) + user_roles + officer_scopes",
)
def invite_officer(
    body: OfficerInviteRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
) -> OfficerInviteResponse:
    from ticketing.services.officer_admin import (
        JurisdictionInput,
        create_scope_row,
        keycloak_configured,
        keycloak_create_user,
        log_admin_audit,
        upsert_user_role_row,
        validate_jurisdiction,
    )

    email = body.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=422, detail="Valid email is required")

    juris = JurisdictionInput(
        organization_id=body.organization_id,
        role_key=body.role_key,
        location_code=body.location_code,
        project_id=body.project_id,
        project_code=body.project_code,
        package_id=body.package_id,
        includes_children=body.includes_children,
    )
    resolved_pc = validate_jurisdiction(db, juris, require_jurisdiction=True)
    role = db.execute(select(Role).where(Role.role_key == body.role_key)).scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail=f"Role not found: {body.role_key}")

    if keycloak_configured():
        keycloak_create_user(email, body.role_key, body.organization_id, body.temp_password)
        onboarding_status = "invited"
    else:
        onboarding_status = "active"

    loc = (body.location_code or "").strip() or None
    upsert_user_role_row(db, email, role, body.organization_id, loc)
    create_scope_row(db, email, juris, resolved_pc)

    ob = db.get(OfficerOnboarding, email)
    if ob:
        ob.status = onboarding_status
        ob.updated_at = datetime.now(timezone.utc)
    else:
        db.add(OfficerOnboarding(user_id=email, status=onboarding_status))

    log_admin_audit(
        db,
        actor_user_id=current_user.user_id,
        action="officer.invite",
        target_user_id=email,
        payload=juris.model_dump(),
    )
    db.commit()

    msg = (
        "Officer created with jurisdiction scope."
        if not keycloak_configured()
        else "Officer invited in Keycloak with jurisdiction scope. "
        "Status becomes Active after first password change (webhook)."
    )
    return OfficerInviteResponse(ok=True, email=email, message=msg)


@router.patch(
    "/users/{user_id}",
    response_model=OfficerUpdateResponse,
    summary="Update officer Keycloak attributes from roster (auth stack)",
)
def update_officer(
    user_id: str,
    body: OfficerUpdateRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
) -> OfficerUpdateResponse:
    from ticketing.services.officer_admin import keycloak_update_user_attributes, log_admin_audit

    if not db.execute(select(UserRole.user_id).where(UserRole.user_id == user_id).limit(1)).scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Officer not found")

    if body.sync_keycloak:
        keycloak_update_user_attributes(
            user_id,
            body.role_keys,
            body.organization_id,
            body.location_code,
        )

    log_admin_audit(
        db,
        actor_user_id=current_user.user_id,
        action="officer.update",
        target_user_id=user_id,
        payload=body.model_dump(),
    )
    db.commit()
    return OfficerUpdateResponse(ok=True, user_id=user_id)


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove officer — all roles/scopes; disable Keycloak user",
)
def delete_officer(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
) -> None:
    from ticketing.services.officer_admin import keycloak_disable_user, log_admin_audit

    roles = db.execute(select(UserRole).where(UserRole.user_id == user_id)).scalars().all()
    scopes = db.execute(select(OfficerScope).where(OfficerScope.user_id == user_id)).scalars().all()
    if not roles and not scopes:
        raise HTTPException(status_code=404, detail="Officer not found")

    for s in scopes:
        db.delete(s)
    for r in roles:
        db.delete(r)
    ob = db.get(OfficerOnboarding, user_id)
    if ob:
        db.delete(ob)

    keycloak_disable_user(user_id)
    log_admin_audit(
        db,
        actor_user_id=current_user.user_id,
        action="officer.disable",
        target_user_id=user_id,
        payload={"roles_removed": len(roles), "scopes_removed": len(scopes)},
    )
    db.commit()


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


@router.get(
    "/users/me/notifications",
    response_model=NotificationsResponse,
    summary="Get unseen notifications for the current officer (for bell panel)",
)
def get_notifications(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> NotificationsResponse:
    """
    Returns the most recent unseen events assigned to the current officer,
    joined with their parent ticket for display context.
    Ordered oldest-first so the panel shows the backlog from top.
    """
    from sqlalchemy import func

    rows = db.execute(
        select(TicketEvent, Ticket.grievance_id, Ticket.grievance_summary)
        .join(Ticket, Ticket.ticket_id == TicketEvent.ticket_id)
        .where(
            TicketEvent.assigned_to_user_id == current_user.user_id,
            TicketEvent.seen.is_(False),
        )
        .order_by(TicketEvent.created_at.asc())
        .limit(limit)
    ).all()

    total_count = db.execute(
        select(func.count(TicketEvent.event_id)).where(
            TicketEvent.assigned_to_user_id == current_user.user_id,
            TicketEvent.seen.is_(False),
        )
    ).scalar_one()

    items = [
        NotificationItem(
            event_id=ev.event_id,
            ticket_id=ev.ticket_id,
            grievance_id=grievance_id,
            grievance_summary=grievance_summary,
            event_type=ev.event_type,
            note=ev.note,
            created_at=ev.created_at,
            created_by_user_id=ev.created_by_user_id,
        )
        for ev, grievance_id, grievance_summary in rows
    ]
    return NotificationsResponse(items=items, total=total_count)
