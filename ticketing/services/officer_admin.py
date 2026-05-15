"""
Officer admin helpers: jurisdiction validation, Keycloak sync, audit logging.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ticketing.config.settings import get_settings
from ticketing.models.admin_audit_log import AdminAuditLog
from ticketing.models.officer_scope import OfficerScope
from ticketing.models.package import ProjectPackage
from ticketing.models.project import Project
from ticketing.models.user import Role, UserRole


class JurisdictionInput(BaseModel):
    organization_id: str
    role_key: str
    location_code: Optional[str] = None
    project_id: Optional[str] = None
    project_code: Optional[str] = None
    package_id: Optional[str] = None
    includes_children: bool = False


def validate_jurisdiction(
    db: Session,
    data: JurisdictionInput,
    *,
    require_jurisdiction: bool = True,
) -> str:
    """
    Validate org + at least one of project/package/location when required.
    Returns resolved project_code for scope rows.
    """
    org_id = data.organization_id.strip()
    if not org_id:
        raise HTTPException(status_code=422, detail="organization_id is required")

    has_loc = bool((data.location_code or "").strip())
    has_proj = bool(data.project_id or (data.project_code or "").strip())
    has_pkg = bool(data.package_id)

    if require_jurisdiction and not (has_loc or has_proj or has_pkg):
        raise HTTPException(
            status_code=422,
            detail="At least one of project, package, or location is required",
        )

    resolved_project_code: Optional[str] = (data.project_code or "").strip() or None
    if data.project_id:
        project = db.get(Project, data.project_id)
        if not project:
            raise HTTPException(status_code=422, detail=f"Project '{data.project_id}' not found")
        resolved_project_code = project.short_code

    if data.package_id:
        pkg = db.get(ProjectPackage, data.package_id)
        if not pkg:
            raise HTTPException(status_code=422, detail=f"Package '{data.package_id}' not found")
        if data.project_id and pkg.project_id != data.project_id:
            raise HTTPException(
                status_code=422,
                detail="package_id does not belong to the selected project",
            )
        if not data.project_id:
            data.project_id = pkg.project_id
            proj = db.get(Project, pkg.project_id)
            if proj:
                resolved_project_code = proj.short_code

    role = db.execute(
        select(Role).where(Role.role_key == data.role_key)
    ).scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail=f"Role not found: {data.role_key}")

    return resolved_project_code or ""


def create_scope_row(
    db: Session,
    user_id: str,
    data: JurisdictionInput,
    resolved_project_code: str,
) -> OfficerScope:
    scope = OfficerScope(
        user_id=user_id,
        role_key=data.role_key,
        organization_id=data.organization_id.strip(),
        location_code=(data.location_code or "").strip() or None,
        project_id=data.project_id,
        project_code=resolved_project_code or None,
        package_id=data.package_id,
        includes_children=data.includes_children,
    )
    db.add(scope)
    return scope


def upsert_user_role_row(
    db: Session,
    user_id: str,
    role: Role,
    organization_id: str,
    location_code: Optional[str],
) -> UserRole:
    existing = db.execute(
        select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.role_id == role.role_id,
            UserRole.organization_id == organization_id,
        )
    ).scalar_one_or_none()
    if existing:
        if location_code is not None:
            existing.location_code = location_code or None
        return existing
    row = UserRole(
        user_id=user_id,
        role_id=role.role_id,
        organization_id=organization_id,
        location_code=location_code,
    )
    db.add(row)
    return row


def log_admin_audit(
    db: Session,
    *,
    actor_user_id: str,
    action: str,
    target_user_id: Optional[str] = None,
    payload: Optional[dict[str, Any]] = None,
) -> None:
    db.add(
        AdminAuditLog(
            actor_user_id=actor_user_id,
            action=action,
            target_user_id=target_user_id,
            payload=payload,
        )
    )


def keycloak_configured() -> bool:
    return bool(get_settings().keycloak_admin_url)


def _keycloak_admin():
    from keycloak import KeycloakAdmin, KeycloakOpenIDConnection

    settings = get_settings()
    conn = KeycloakOpenIDConnection(
        server_url=settings.keycloak_admin_url.rstrip("/") + "/",
        username="admin",
        password=settings.keycloak_admin_password,
        realm_name="grm",
        user_realm_name="master",
        verify=True,
    )
    return KeycloakAdmin(connection=conn)


def keycloak_create_user(
    email: str,
    role_key: str,
    organization_id: str,
    temp_password: Optional[str] = None,
) -> None:
    admin = _keycloak_admin()
    try:
        admin.create_user({
            "username": email,
            "email": email,
            "enabled": True,
            "attributes": {
                "grm_roles": role_key,
                "organization_id": organization_id,
            },
            "credentials": [{
                "type": "password",
                "value": temp_password or "GrmDemo2026!",
                "temporary": True,
            }],
            "requiredActions": ["UPDATE_PASSWORD"],
        })
    except Exception as exc:
        err = str(exc)
        if "409" in err or "already exists" in err.lower():
            raise HTTPException(status_code=409, detail=f"User {email!r} already exists in Keycloak")
        raise HTTPException(status_code=500, detail=f"Keycloak error: {err}")


def keycloak_update_user_attributes(
    user_id: str,
    role_keys: list[str],
    organization_id: str,
    location_code: Optional[str] = None,
) -> None:
    if not keycloak_configured():
        return
    admin = _keycloak_admin()
    kc_users = admin.get_users(query={"username": user_id, "exact": True})
    if not kc_users:
        kc_users = admin.get_users(query={"email": user_id, "exact": True})
    if not kc_users:
        return
    kc_id = kc_users[0]["id"]
    attrs: dict[str, list[str]] = {
        "grm_roles": [",".join(role_keys) if role_keys else ""],
        "organization_id": [organization_id],
    }
    if location_code:
        attrs["location_code"] = [location_code]
    admin.update_user(user_id=kc_id, payload={"attributes": attrs})


def keycloak_disable_user(user_id: str) -> None:
    if not keycloak_configured():
        return
    admin = _keycloak_admin()
    kc_users = admin.get_users(query={"username": user_id, "exact": True})
    if not kc_users:
        kc_users = admin.get_users(query={"email": user_id, "exact": True})
    if not kc_users:
        return
    admin.update_user(user_id=kc_users[0]["id"], payload={"enabled": False})
