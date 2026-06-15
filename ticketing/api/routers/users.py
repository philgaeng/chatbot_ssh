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
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ticketing.api.dependencies import (
    CurrentUser,
    get_authenticated_user,
    get_current_user,
    get_db,
    require_admin,
    require_super_admin,
)
from ticketing.api.schemas.user import (
    AdminContextResponse,
    AdminScopeCreate,
    AdminScopeResponse,
    NotificationBadgeResponse,
    NotificationItem,
    NotificationsResponse,
    RoleCreate,
    RoleResponse,
    RoleUpdate,
    UserRoleCreate,
    UserRoleResponse,
)
from ticketing.constants.role_archetypes import (
    list_archetypes,
    permissions_for_archetype,
    slugify_role_key,
    validate_operational_permissions,
)
from ticketing.models.admin_scope import AdminScope
from ticketing.services.admin_access import (
    ADMIN_ROLE_KEYS,
    SettingsAction,
    admin_context_payload,
    can_create_operational_role,
    is_country_admin,
    is_super_admin,
    require_settings_write,
)
from ticketing.models.officer_scope import OfficerScope
from ticketing.models.officer_onboarding import OfficerOnboarding
from ticketing.models.ticket import Ticket, TicketEvent
from ticketing.models.user import Role, UserRole
from ticketing.models.workflow import WorkflowStep

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

def _role_usage_counts(db: Session, role_key: str) -> tuple[int, int]:
    steps = db.scalar(
        select(func.count())
        .select_from(WorkflowStep)
        .where(
            WorkflowStep.assigned_role_key == role_key,
            WorkflowStep.is_deleted.is_(False),
        )
    ) or 0
    role_row = db.execute(select(Role).where(Role.role_key == role_key)).scalar_one_or_none()
    officers = 0
    if role_row:
        officers = db.scalar(
            select(func.count()).select_from(UserRole).where(UserRole.role_id == role_row.role_id)
        ) or 0
        officers += db.scalar(
            select(func.count())
            .select_from(OfficerScope)
            .where(OfficerScope.role_key == role_key)
        ) or 0
    return steps, officers


def _role_to_response(db: Session, role: Role) -> RoleResponse:
    steps, officers = _role_usage_counts(db, role.role_key)
    return RoleResponse(
        role_id=role.role_id,
        role_key=role.role_key,
        display_name=role.display_name,
        description=role.description,
        workflow_scope=role.workflow_scope,
        jurisdiction_mode=role.jurisdiction_mode,
        permissions=role.permissions,
        role_kind=role.role_kind,
        role_origin=role.role_origin,
        steps_count=steps,
        officers_count=officers,
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


@router.get("/roles/archetypes", summary="List role archetype templates")
def get_role_archetypes(
    _: CurrentUser = Depends(get_authenticated_user),
) -> list[dict[str, str]]:
    return list_archetypes()


@router.get("/roles", response_model=list[RoleResponse], summary="List GRM roles")
def list_roles(
    kind: str = "operational",
    workflow_track: Optional[str] = None,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_authenticated_user),
) -> list[RoleResponse]:
    stmt = select(Role).order_by(Role.role_key)
    if kind == "admin":
        stmt = stmt.where(Role.role_kind == "admin")
    elif kind == "operational":
        stmt = stmt.where(Role.role_kind == "operational")
    roles = db.execute(stmt).scalars().all()
    if workflow_track:
        wt = workflow_track.lower()
        if wt == "standard":
            roles = [r for r in roles if r.workflow_scope in ("Standard", "Both", None)]
        elif wt == "seah":
            roles = [r for r in roles if r.workflow_scope in ("SEAH", "Both", None)]
    return [_role_to_response(db, r) for r in roles]


@router.post(
    "/roles",
    response_model=RoleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create custom operational role",
)
def create_role(
    body: RoleCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> RoleResponse:
    track = "seah" if body.workflow_scope == "SEAH" else "standard"
    require_settings_write(current_user, SettingsAction.CREATE_OPERATIONAL_ROLE, track=track)

    role_key = (body.role_key or slugify_role_key(body.display_name)).strip().lower()
    if not role_key or role_key in ADMIN_ROLE_KEYS:
        raise HTTPException(status_code=422, detail="Invalid or reserved role_key")

    existing = db.execute(select(Role).where(Role.role_key == role_key)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail=f"role_key already exists: {role_key}")

    try:
        perms = body.permissions if body.permissions is not None else permissions_for_archetype(
            body.archetype, workflow_scope=body.workflow_scope
        )
        validate_operational_permissions(perms)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    role = Role(
        role_key=role_key,
        display_name=body.display_name.strip(),
        description=(body.description or "").strip() or None,
        workflow_scope=body.workflow_scope,
        jurisdiction_mode=body.jurisdiction_mode,
        permissions=perms,
        role_kind="operational",
        role_origin="custom",
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    return _role_to_response(db, role)


@router.patch(
    "/roles/{role_id}",
    response_model=RoleResponse,
    summary="Update role catalog fields (admin)",
)
def update_role(
    role_id: str,
    body: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> RoleResponse:
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    if role.role_kind == "admin" and not current_user.is_super_admin:
        raise HTTPException(status_code=403, detail="Admin roles editable by super_admin only")

    if role.role_origin == "system" and body.permissions is not None and not current_user.is_super_admin:
        raise HTTPException(status_code=403, detail="System role permissions require super_admin")

    if role.role_kind == "operational" and role.role_origin == "custom":
        track = "seah" if role.workflow_scope == "SEAH" else "standard"
        if not can_create_operational_role(current_user, track=track) and not current_user.is_super_admin:
            raise HTTPException(status_code=403, detail="Country admin required for this track")

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
    if body.jurisdiction_mode is not None:
        from ticketing.constants.jurisdiction import VALID_JURISDICTION_MODES

        v = body.jurisdiction_mode.strip().lower()
        if v and v not in VALID_JURISDICTION_MODES:
            raise HTTPException(
                status_code=422,
                detail="jurisdiction_mode must be field, country, global, or empty",
            )
        role.jurisdiction_mode = v or None
    if body.permissions is not None:
        try:
            validate_operational_permissions(body.permissions)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        role.permissions = body.permissions
    role.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(role)
    return _role_to_response(db, role)


@router.delete(
    "/roles/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete role from catalog (admin)",
)
def delete_role(
    role_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> None:
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    if role.role_origin == "system" and not current_user.is_super_admin:
        raise HTTPException(status_code=403, detail="System roles deletable by super_admin only")

    steps, officers = _role_usage_counts(db, role.role_key)
    if steps or officers:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Role is in use",
                "steps_count": steps,
                "officers_count": officers,
            },
        )

    db.delete(role)
    db.commit()


# ── Admin scopes ──────────────────────────────────────────────────────────────

def _resolve_project_ref(db: Session, project_ref: str | None) -> str | None:
    if not project_ref:
        return None
    from ticketing.models.project import Project

    row = db.get(Project, project_ref)
    if row:
        return row.short_code
    row = db.execute(
        select(Project).where(Project.short_code == project_ref)
    ).scalar_one_or_none()
    return row.short_code if row else project_ref


@router.get(
    "/users/me/admin-context",
    response_model=AdminContextResponse,
    summary="Current officer admin matrix context",
)
def get_my_admin_context(
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> AdminContextResponse:
    return AdminContextResponse(**admin_context_payload(current_user))


def _admin_scope_response(
    db: Session,
    scope: AdminScope,
    *,
    onboarding_status: str | None = None,
    invite_email_sent: bool = False,
) -> AdminScopeResponse:
    from ticketing.services.officer_admin import (
        admin_scope_can_send_setup_email,
        officer_eligible_for_invite_resend,
    )

    email = scope.user_id.strip().lower()
    return AdminScopeResponse(
        admin_scope_id=scope.admin_scope_id,
        user_id=email,
        role_key=scope.role_key,
        country_code=scope.country_code,
        project_id=scope.project_id,
        organization_id=scope.organization_id,
        package_id=scope.package_id,
        workflow_track=scope.workflow_track,
        created_at=scope.created_at,
        created_by_user_id=scope.created_by_user_id,
        can_resend_invite=officer_eligible_for_invite_resend(db, email),
        can_send_setup_email=admin_scope_can_send_setup_email(),
        onboarding_status=onboarding_status,
        invite_email_sent=invite_email_sent,
    )


@router.get(
    "/admin-scopes",
    response_model=list[AdminScopeResponse],
    summary="List admin scope assignments",
)
def list_admin_scopes(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> list[AdminScopeResponse]:
    if current_user.is_super_admin:
        rows = db.execute(select(AdminScope).order_by(AdminScope.created_at.desc())).scalars().all()
    else:
        rows = db.execute(
            select(AdminScope).where(AdminScope.user_id == current_user.user_id)
        ).scalars().all()
    return [_admin_scope_response(db, scope) for scope in rows]


@router.post(
    "/admin-scopes",
    response_model=AdminScopeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Appoint country_admin or project_admin",
)
def create_admin_scope(
    body: AdminScopeCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> AdminScopeResponse:
    try:
        tracks = AdminScopeCreate.resolved_workflow_tracks(body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if body.role_key == "country_admin":
        if not current_user.is_super_admin:
            raise HTTPException(status_code=403, detail="Only super_admin may appoint country_admin")
        if not body.country_code:
            raise HTTPException(status_code=422, detail="country_code required for country_admin")
    elif body.role_key == "project_admin":
        if len(tracks) != 1:
            raise HTTPException(
                status_code=422,
                detail="project_admin requires exactly one workflow_track",
            )
        if not (current_user.is_super_admin or is_country_admin(current_user, tracks[0])):  # type: ignore[arg-type]
            raise HTTPException(
                status_code=403,
                detail="country_admin (matching track) or super_admin required",
            )
        if not body.project_id:
            raise HTTPException(status_code=422, detail="project_id required for project_admin")
    else:
        raise HTTPException(status_code=422, detail="Invalid role_key")

    project_ref = _resolve_project_ref(db, body.project_id)
    role = db.execute(select(Role).where(Role.role_key == body.role_key)).scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail=f"Role not found: {body.role_key}")

    from ticketing.services.officer_admin import log_admin_audit, provision_admin_scope_keycloak

    email = body.user_id.strip().lower()
    org_id = (body.organization_id or "DOR").strip()
    created_scopes: list[AdminScope] = []
    onboarding_status = "active"

    for track in tracks:
        dup_stmt = select(AdminScope).where(
            AdminScope.user_id == email,
            AdminScope.role_key == body.role_key,
            AdminScope.workflow_track == track,
        )
        if body.role_key == "country_admin":
            dup_stmt = dup_stmt.where(AdminScope.country_code == body.country_code)
        else:
            dup_stmt = dup_stmt.where(AdminScope.project_id == project_ref)
        existing = db.execute(dup_stmt).scalar_one_or_none()
        if existing:
            created_scopes.append(existing)
            continue

        scope = AdminScope(
            user_id=email,
            role_key=body.role_key,
            country_code=body.country_code,
            project_id=project_ref,
            organization_id=body.organization_id,
            package_id=body.package_id,
            workflow_track=track,
            created_by_user_id=current_user.user_id,
        )
        db.add(scope)
        created_scopes.append(scope)

    existing_ur = db.execute(
        select(UserRole).where(
            UserRole.user_id == email,
            UserRole.role_id == role.role_id,
            UserRole.organization_id == org_id,
        )
    ).scalar_one_or_none()
    if not existing_ur:
        db.add(
            UserRole(
                user_id=email,
                role_id=role.role_id,
                organization_id=org_id,
            )
        )
    db.flush()
    onboarding_status = provision_admin_scope_keycloak(db, email, body.role_key, org_id)
    log_admin_audit(
        db,
        actor_user_id=current_user.user_id,
        action="admin_scope.appoint",
        target_user_id=email,
        payload={
            "role_key": body.role_key,
            "country_code": body.country_code,
            "project_id": project_ref,
            "organization_id": org_id,
            "workflow_tracks": tracks,
            "onboarding_status": onboarding_status,
        },
    )
    db.commit()
    primary = created_scopes[0]
    db.refresh(primary)
    return _admin_scope_response(
        db,
        primary,
        onboarding_status=onboarding_status,
        invite_email_sent=onboarding_status == "invited",
    )


@router.post(
    "/admin-scopes/{admin_scope_id}/send-invite",
    response_model=AdminScopeResponse,
    summary="Send Keycloak setup email for an admin-scope officer",
)
def send_admin_scope_invite(
    admin_scope_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> AdminScopeResponse:
    from ticketing.services.officer_admin import log_admin_audit, provision_admin_scope_keycloak

    scope = db.get(AdminScope, admin_scope_id)
    if not scope:
        raise HTTPException(status_code=404, detail="Admin scope not found")
    if scope.role_key == "country_admin" and not current_user.is_super_admin:
        raise HTTPException(status_code=403, detail="Only super_admin may manage country_admin")
    if scope.role_key == "project_admin" and not (
        current_user.is_super_admin or is_country_admin(current_user, scope.workflow_track)  # type: ignore[arg-type]
    ):
        raise HTTPException(status_code=403, detail="Insufficient permissions for this admin scope")

    email = scope.user_id.strip().lower()
    org_id = (scope.organization_id or "DOR").strip()
    onboarding_status = provision_admin_scope_keycloak(
        db,
        email,
        scope.role_key,
        org_id,
        force_invite=True,
    )
    log_admin_audit(
        db,
        actor_user_id=current_user.user_id,
        action="admin_scope.send_invite",
        target_user_id=email,
        payload={"admin_scope_id": admin_scope_id, "onboarding_status": onboarding_status},
    )
    db.commit()
    db.refresh(scope)
    return _admin_scope_response(
        db,
        scope,
        onboarding_status=onboarding_status,
        invite_email_sent=onboarding_status == "invited",
    )


@router.delete(
    "/admin-scopes/{admin_scope_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke admin scope assignment",
)
def delete_admin_scope(
    admin_scope_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> None:
    scope = db.get(AdminScope, admin_scope_id)
    if not scope:
        raise HTTPException(status_code=404, detail="Admin scope not found")
    if not current_user.is_super_admin and scope.created_by_user_id != current_user.user_id:
        if scope.user_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="Cannot revoke this assignment")
    db.delete(scope)
    from ticketing.services.officer_admin import sync_officer_keycloak_roles

    sync_officer_keycloak_roles(db, scope.user_id)
    db.commit()


# ── User roles ─────────────────────────────────────────────────────────────────

@router.get(
    "/users/{user_id}/roles",
    response_model=list[UserRoleResponse],
    summary="List role assignments for an officer",
)
def get_user_roles(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
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
    current_user: CurrentUser = Depends(require_admin),
) -> UserRole:

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
    from ticketing.services.officer_admin import sync_officer_keycloak_roles

    sync_officer_keycloak_roles(db, user_id)
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
    current_user: CurrentUser = Depends(require_admin),
) -> None:
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
    from ticketing.services.officer_admin import sync_officer_keycloak_roles

    sync_officer_keycloak_roles(db, user_id)
    db.commit()


# ── Officers list (for assign dropdown) ──────────────────────────────────────

class OfficerBrief(BaseModel):
    user_id: str
    role_keys: list[str]
    organization_id: str | None = None
    location_code: str | None = None


class OfficerRosterScopeBrief(BaseModel):
    role_key: str
    organization_id: str
    project_code: str | None = None
    project_id: str | None = None
    package_id: str | None = None
    location_code: str | None = None


class OfficerRosterEntry(BaseModel):
    """One officer identity with all role rows aggregated from ticketing.user_roles."""

    user_id: str
    display_name: str
    email: str | None = None
    phone_number: str | None = None
    role_keys: list[str]
    organization_ids: list[str]
    location_codes: list[str]
    project_codes: list[str] = []
    package_ids: list[str] = []
    scopes: list[OfficerRosterScopeBrief] = []
    onboarding_status: str = "active"  # invited | active


@router.get(
    "/users/roster",
    response_model=list[OfficerRosterEntry],
    summary="List officers for Settings UI — Keycloak identity + DB jurisdiction",
)
def list_officer_roster(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
) -> list[OfficerRosterEntry]:
    """
    Admin roster: merge Keycloak officer accounts with ticketing.user_roles /
    officer_scopes. user_id is always the Keycloak email when auth is enabled.
    """
    from ticketing.services.keycloak_users import list_grm_officer_profiles

    kc_profiles = list_grm_officer_profiles()
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

    from ticketing.services.officer_admin import sync_officer_onboarding_status

    roster_synced = False
    for uid in order:
        if onboard_map.get(uid) != "invited":
            continue
        if sync_officer_onboarding_status(db, uid):
            onboard_map[uid] = "active"
            roster_synced = True
    if roster_synced:
        db.commit()

    proj_by: dict[str, set[str]] = defaultdict(set)
    pkg_by: dict[str, set[str]] = defaultdict(set)
    scope_detail_by: dict[str, list[OfficerRosterScopeBrief]] = defaultdict(list)

    # Include enabled Keycloak officers not yet in user_roles (invited, pending DB sync).
    for email, profile in kc_profiles.items():
        if email not in role_keys_by:
            role_keys_by[email] = list(profile.role_keys)
            order.append(email)
            if profile.organization_id:
                orgs_by[email].add(profile.organization_id)

    if order:
        scope_rows = db.execute(
            select(
                OfficerScope.user_id,
                OfficerScope.role_key,
                OfficerScope.organization_id,
                OfficerScope.project_code,
                OfficerScope.project_id,
                OfficerScope.package_id,
                OfficerScope.location_code,
            ).where(OfficerScope.user_id.in_(order))
        ).all()
        for uid, role_key, org_id, pcode, proj_id, pkg_id, scope_loc in scope_rows:
            scope_detail_by[uid].append(
                OfficerRosterScopeBrief(
                    role_key=role_key,
                    organization_id=org_id,
                    project_code=pcode,
                    project_id=proj_id,
                    package_id=pkg_id,
                    location_code=scope_loc,
                )
            )
            if pcode:
                proj_by[uid].add(pcode)
            if pkg_id:
                pkg_by[uid].add(pkg_id)
            if scope_loc:
                locs_by[uid].add(scope_loc)

    def _entry(uid: str) -> OfficerRosterEntry:
        kc = kc_profiles.get(uid.lower()) if "@" in uid else None
        effective_keys: list[str] = []
        seen_rk: set[str] = set()
        for rk in role_keys_by.get(uid, []):
            if rk not in seen_rk:
                seen_rk.add(rk)
                effective_keys.append(rk)
        for scope in scope_detail_by.get(uid, []):
            if scope.role_key and scope.role_key not in seen_rk:
                seen_rk.add(scope.role_key)
                effective_keys.append(scope.role_key)
        return OfficerRosterEntry(
            user_id=uid,
            display_name=kc.display_name if kc else _display_name_from_user_id(uid),
            email=kc.email if kc else _email_hint(uid),
            phone_number=(kc.phone_number if kc and kc.phone_number else None),
            role_keys=effective_keys,
            organization_ids=sorted(orgs_by[uid]),
            location_codes=sorted(locs_by[uid]),
            project_codes=sorted(proj_by.get(uid, set())),
            package_ids=sorted(pkg_by.get(uid, set())),
            scopes=scope_detail_by.get(uid, []),
            onboarding_status=onboard_map.get(uid, "active"),
        )

    # Keycloak order first (alphabetic by display name), then legacy non-email ids.
    email_ids = [uid for uid in order if "@" in uid]
    other_ids = [uid for uid in order if "@" not in uid]
    email_ids.sort(
        key=lambda uid: (
            kc_profiles.get(uid.lower()).display_name if uid.lower() in kc_profiles
            else _display_name_from_user_id(uid)
        ).lower()
    )
    other_ids.sort()

    return [_entry(uid) for uid in email_ids + other_ids]


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
    current_user: CurrentUser = Depends(get_authenticated_user),
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
    current_user: CurrentUser = Depends(require_admin),
) -> OfficerScope:
    from ticketing.services.officer_admin import JurisdictionInput, validate_jurisdiction

    juris = JurisdictionInput(
        organization_id=payload.organization_id,
        role_key=payload.role_key,
        location_code=payload.location_code,
        project_id=payload.project_id,
        project_code=payload.project_code,
        package_id=payload.package_id,
        includes_children=payload.includes_children,
    )
    resolved_project_code = validate_jurisdiction(db, juris, require_jurisdiction=True) or None

    existing_orgs = {
        row
        for row in db.execute(
            select(OfficerScope.organization_id).where(OfficerScope.user_id == user_id)
        ).scalars().all()
    }
    if existing_orgs and payload.organization_id not in existing_orgs:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Officers may only belong to one organization. "
                f"Existing scopes use {sorted(existing_orgs)[0]!r}; "
                "remove other scopes before adding a different organization."
            ),
        )

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
    db.flush()  # assign scope_id before audit row references it
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
    from ticketing.services.officer_admin import sync_officer_keycloak_roles

    sync_officer_keycloak_roles(db, user_id)
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
    current_user: CurrentUser = Depends(require_admin),
) -> None:
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
    from ticketing.services.officer_admin import sync_officer_keycloak_roles

    sync_officer_keycloak_roles(db, user_id)
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


# ── Officer self-service profile (Keycloak) ───────────────────────────────────

class OfficerSessionResponse(BaseModel):
    """Effective permissions context for the signed-in officer (DB-derived)."""
    user_id: str
    role_keys: list[str]
    organization_id: Optional[str] = None


@router.get(
    "/users/me/session",
    response_model=OfficerSessionResponse,
    summary="Current officer session — effective role keys from DB scopes + roster",
)
def get_my_session(
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> OfficerSessionResponse:
    return OfficerSessionResponse(
        user_id=current_user.user_id,
        role_keys=list(current_user.role_keys),
        organization_id=current_user.organization_id or None,
    )


# ── Officer self-service profile (Keycloak) ───────────────────────────────────

from ticketing.services.officer_profile import (
    OfficerProfilePatch,
    OfficerProfileResponse,
    get_officer_profile,
    update_officer_profile,
)


@router.get(
    "/users/me/profile",
    response_model=OfficerProfileResponse,
    summary="Current officer profile (name, phone, position)",
)
def get_my_profile(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> OfficerProfileResponse:
    return get_officer_profile(db, current_user.user_id)


@router.patch(
    "/users/me/profile",
    response_model=OfficerProfileResponse,
    summary="Update current officer profile in Keycloak",
)
def patch_my_profile(
    body: OfficerProfilePatch,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> OfficerProfileResponse:
    return update_officer_profile(db, current_user.user_id, body)


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


class KeycloakInvitePreflightResponse(BaseModel):
    ok: bool
    configured: bool
    keycloak_reachable: bool
    realm: str
    smtp_configured: bool
    missing_smtp_fields: list[str]
    email_action_supported: bool
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


@router.get(
    "/users/invite/preflight",
    response_model=KeycloakInvitePreflightResponse,
    summary="Preflight check for Keycloak invite-email readiness",
)
def invite_preflight(
    _: CurrentUser = Depends(require_admin),
) -> KeycloakInvitePreflightResponse:
    from ticketing.services.officer_admin import keycloak_invite_preflight

    return KeycloakInvitePreflightResponse(**keycloak_invite_preflight())


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
    from ticketing.services.officer_admin import sync_officer_keycloak_roles

    sync_officer_keycloak_roles(db, email)
    db.commit()

    msg = (
        "Officer created with jurisdiction scope."
        if not keycloak_configured()
        else "Officer invited in Keycloak; setup email sent with required actions. "
        "Status becomes Active after first password change (webhook)."
    )
    return OfficerInviteResponse(ok=True, email=email, message=msg)


@router.post(
    "/users/{user_id}/resend-invite",
    response_model=OfficerInviteResponse,
    summary="Resend Keycloak setup email for an invited officer (fresh action link)",
)
def resend_officer_invite(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
) -> OfficerInviteResponse:
    from ticketing.services.officer_admin import (
        keycloak_resend_invite_email,
        log_admin_audit,
        officer_eligible_for_invite_resend,
    )

    email = user_id.strip().lower()
    if not officer_eligible_for_invite_resend(db, email):
        raise HTTPException(
            status_code=400,
            detail="Resend invite is only available while Keycloak onboarding is incomplete.",
        )

    sent_to = keycloak_resend_invite_email(email, db=db)

    log_admin_audit(
        db,
        actor_user_id=current_user.user_id,
        action="officer.invite.resend",
        target_user_id=email,
        payload={},
    )
    db.commit()

    return OfficerInviteResponse(
        ok=True,
        email=sent_to,
        message=(
            f"Setup email resent to {sent_to}. "
            "The new link expires in 7 days (check spam if needed)."
        ),
    )


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
    from ticketing.services.officer_admin import (
        apply_officer_organization,
        log_admin_audit,
        sync_officer_keycloak_roles,
    )

    if not db.execute(select(UserRole.user_id).where(UserRole.user_id == user_id).limit(1)).scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Officer not found")

    roles_updated, scopes_updated = apply_officer_organization(
        db, user_id, body.organization_id
    )

    if body.sync_keycloak:
        sync_officer_keycloak_roles(db, user_id)

    audit_payload = {
        **body.model_dump(),
        "roles_updated": roles_updated,
        "scopes_updated": scopes_updated,
    }
    log_admin_audit(
        db,
        actor_user_id=current_user.user_id,
        action="officer.update",
        target_user_id=user_id,
        payload=audit_payload,
    )
    db.commit()
    return OfficerUpdateResponse(ok=True, user_id=user_id)


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove officer — DB roles/scopes and Keycloak realm user",
)
def delete_officer(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
) -> None:
    from ticketing.services.officer_admin import keycloak_delete_user, log_admin_audit

    roles = db.execute(select(UserRole).where(UserRole.user_id == user_id)).scalars().all()
    scopes = db.execute(select(OfficerScope).where(OfficerScope.user_id == user_id)).scalars().all()
    had_db = bool(roles or scopes)
    kc_deleted = keycloak_delete_user(user_id)
    if not had_db and not kc_deleted:
        raise HTTPException(status_code=404, detail="Officer not found")

    for s in scopes:
        db.delete(s)
    for r in roles:
        db.delete(r)
    ob = db.get(OfficerOnboarding, user_id)
    if ob:
        db.delete(ob)
    log_admin_audit(
        db,
        actor_user_id=current_user.user_id,
        action="officer.delete",
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
