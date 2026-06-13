"""
Admin permission matrix — tier + workflow_track enforcement.

See docs/ticketing_system/11_roles_and_permissions.md §2.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Literal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ticketing.models.admin_scope import WORKFLOW_TRACKS, AdminScope

if TYPE_CHECKING:
    from ticketing.api.dependencies import CurrentUser

WorkflowTrack = Literal["standard", "seah"]

ADMIN_ROLE_KEYS = frozenset({"super_admin", "country_admin", "project_admin"})


@dataclass(frozen=True)
class AdminScopeRow:
    admin_scope_id: str
    user_id: str
    role_key: str
    country_code: str | None
    project_id: str | None
    organization_id: str | None
    package_id: str | None
    workflow_track: str

    @classmethod
    def from_model(cls, row: AdminScope) -> AdminScopeRow:
        return cls(
            admin_scope_id=row.admin_scope_id,
            user_id=row.user_id,
            role_key=row.role_key,
            country_code=row.country_code,
            project_id=row.project_id,
            organization_id=row.organization_id,
            package_id=row.package_id,
            workflow_track=row.workflow_track,
        )


class SettingsAction(str, Enum):
    PLATFORM_SETTINGS = "platform_settings"
    CREATE_PROJECT = "create_project"
    MANAGE_STRUCTURE = "manage_structure"
    MANAGE_SEAH_SETTINGS = "manage_seah_settings"
    MANAGE_WORKFLOWS = "manage_workflows"
    CREATE_OPERATIONAL_ROLE = "create_operational_role"
    INVITE_OFFICERS = "invite_officers"
    MANAGE_PROJECT = "manage_project"


def load_admin_scopes(db: Session, user_id: str) -> list[AdminScopeRow]:
    rows = db.execute(
        select(AdminScope).where(AdminScope.user_id == user_id)
    ).scalars().all()
    return [AdminScopeRow.from_model(r) for r in rows]


def _normalize_track(track: str | None) -> WorkflowTrack | None:
    if track is None:
        return None
    t = track.lower()
    if t in WORKFLOW_TRACKS:
        return t  # type: ignore[return-value]
    return None


def is_super_admin(user: CurrentUser) -> bool:
    return "super_admin" in user.role_keys


def is_country_admin(user: CurrentUser, track: WorkflowTrack | None = None) -> bool:
    scopes = getattr(user, "admin_scopes", []) or []
    for s in scopes:
        if s.role_key != "country_admin":
            continue
        if track is None or s.workflow_track == track:
            return True
    return False


def is_project_admin(
    user: CurrentUser,
    project_id: str | None = None,
    track: WorkflowTrack | None = None,
) -> bool:
    scopes = getattr(user, "admin_scopes", []) or []
    for s in scopes:
        if s.role_key != "project_admin":
            continue
        if project_id and s.project_id != project_id:
            continue
        if track and s.workflow_track != track:
            continue
        return True
    return False


def admin_workflow_tracks(user: CurrentUser) -> set[str]:
    if is_super_admin(user):
        return set(WORKFLOW_TRACKS)
    tracks: set[str] = set()
    for s in getattr(user, "admin_scopes", []) or []:
        tracks.add(s.workflow_track)
    return tracks


def admin_project_ids(user: CurrentUser) -> list[str]:
    return sorted({
        s.project_id
        for s in getattr(user, "admin_scopes", []) or []
        if s.role_key == "project_admin" and s.project_id
    })


def admin_country_codes(user: CurrentUser) -> list[str]:
    return sorted({
        s.country_code
        for s in getattr(user, "admin_scopes", []) or []
        if s.role_key == "country_admin" and s.country_code
    })


def can_access_platform_settings(user: CurrentUser) -> bool:
    return is_super_admin(user)


def can_create_project(user: CurrentUser) -> bool:
    if is_super_admin(user):
        return True
    return is_country_admin(user)


def can_manage_structure(user: CurrentUser, *, track: str = "standard") -> bool:
    """Country admins manage project structure same as super_admin on Settings → Projects."""
    if is_super_admin(user):
        return True
    return is_country_admin(user)


def can_manage_seah_settings(user: CurrentUser) -> bool:
    if is_super_admin(user):
        return True
    return is_country_admin(user, "seah")


def can_create_operational_role(user: CurrentUser, *, track: str) -> bool:
    if is_super_admin(user):
        return True
    t = _normalize_track(track)
    if t is None:
        return False
    return is_country_admin(user, t)


def can_see_seah_extended(user: CurrentUser) -> bool:
    from ticketing.models.user import SEAH_ROLES

    if bool(set(user.role_keys) & SEAH_ROLES):
        return True
    if is_super_admin(user) or "adb_hq_exec" in user.role_keys:
        return True
    for s in getattr(user, "admin_scopes", []) or []:
        if s.workflow_track == "seah":
            return True
    return False


def can_view_archived(user: CurrentUser) -> bool:
    if is_super_admin(user):
        return True
    scopes = getattr(user, "admin_scopes", []) or []
    if scopes:
        return True
    # transitional
    return "local_admin" in user.role_keys


def is_any_admin(user: CurrentUser) -> bool:
    """Transitional blanket admin check — prefer specific matrix helpers."""
    if is_super_admin(user):
        return True
    scopes = getattr(user, "admin_scopes", []) or []
    if scopes:
        return True
    return "local_admin" in user.role_keys


def require_track_for_mutation(user: CurrentUser, required_track: str) -> None:
    track = _normalize_track(required_track)
    if track is None:
        raise HTTPException(status_code=422, detail="Invalid workflow_track")
    if is_super_admin(user):
        return
    if track in admin_workflow_tracks(user):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"requires admin scope with workflow_track={track}",
    )


def require_settings_write(user: CurrentUser, action: SettingsAction, *, track: str | None = None) -> None:
    if action == SettingsAction.PLATFORM_SETTINGS:
        if not can_access_platform_settings(user):
            raise HTTPException(status_code=403, detail="Super admin required for platform settings")
        return

    if action == SettingsAction.CREATE_PROJECT:
        if not can_create_project(user):
            raise HTTPException(
                status_code=403,
                detail="requires country_admin or super_admin",
            )
        return

    if action == SettingsAction.MANAGE_STRUCTURE:
        if not can_manage_structure(user, track=track or "standard"):
            raise HTTPException(
                status_code=403,
                detail="requires country_admin track=standard",
            )
        return

    if action == SettingsAction.MANAGE_SEAH_SETTINGS:
        if not can_manage_seah_settings(user):
            raise HTTPException(status_code=403, detail="SEAH country admin or super admin required")
        return

    if action == SettingsAction.CREATE_OPERATIONAL_ROLE:
        if not can_create_operational_role(user, track=track or "standard"):
            raise HTTPException(status_code=403, detail="Country admin required to create operational roles")
        return

    if action == SettingsAction.MANAGE_WORKFLOWS:
        if is_super_admin(user):
            return
        t = _normalize_track(track)
        if t and is_country_admin(user, t):
            return
        raise HTTPException(status_code=403, detail="Workflow admin access required for this track")

    if action == SettingsAction.INVITE_OFFICERS:
        if is_super_admin(user) or is_country_admin(user) or is_project_admin(user):
            return
        if is_any_admin(user):
            return
        raise HTTPException(status_code=403, detail="Admin access required to invite officers")

    if action == SettingsAction.MANAGE_PROJECT:
        if is_super_admin(user) or is_country_admin(user) or is_project_admin(user):
            return
        raise HTTPException(status_code=403, detail="Project admin access required")


def workflow_track_from_type(workflow_type: str) -> WorkflowTrack:
    return "seah" if workflow_type == "seah" else "standard"


def can_mutate_workflow(user: CurrentUser, workflow_type: str) -> bool:
    track = workflow_track_from_type(workflow_type)
    if is_super_admin(user):
        return True
    return is_country_admin(user, track)


def can_assign_project_workflow(user: CurrentUser, workflow_type: str) -> bool:
    """Country admin may assign bindings on their workflow_track; super_admin all."""
    if is_super_admin(user):
        return True
    track: WorkflowTrack = "seah" if workflow_type == "seah" else "standard"
    return is_country_admin(user, track)


def admin_context_payload(user: CurrentUser) -> dict:
    scopes = getattr(user, "admin_scopes", []) or []
    return {
        "is_super_admin": is_super_admin(user),
        "is_country_admin": any(s.role_key == "country_admin" for s in scopes),
        "is_project_admin": any(s.role_key == "project_admin" for s in scopes),
        "admin_workflow_tracks": sorted(admin_workflow_tracks(user)),
        "admin_project_ids": admin_project_ids(user),
        "admin_country_codes": admin_country_codes(user),
        "can_access_platform_settings": can_access_platform_settings(user),
        "can_manage_structure": can_manage_structure(user),
        "can_create_project": can_create_project(user),
        "admin_scopes": [
            {
                "admin_scope_id": s.admin_scope_id,
                "user_id": s.user_id,
                "role_key": s.role_key,
                "country_code": s.country_code,
                "project_id": s.project_id,
                "organization_id": s.organization_id,
                "package_id": s.package_id,
                "workflow_track": s.workflow_track,
            }
            for s in scopes
        ],
    }
