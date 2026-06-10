"""
Officer admin helpers: jurisdiction validation, Keycloak sync, audit logging.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ticketing.config.settings import get_settings
from ticketing.models.admin_audit_log import AdminAuditLog
from ticketing.models.officer_onboarding import OfficerOnboarding
from ticketing.models.officer_scope import OfficerScope
from ticketing.models.package import ProjectPackage
from ticketing.models.project import Project
from ticketing.models.user import Role, UserRole
from ticketing.services.officer_jurisdiction import scope_requires_field_jurisdiction
from ticketing.services.project_routing import resolve_ticket_organization


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
        if scope_requires_field_jurisdiction(db, data.role_key):
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

    if scope_requires_field_jurisdiction(db, data.role_key) and (
        data.project_id or resolved_project_code or data.package_id
    ):
        routed = resolve_ticket_organization(
            db,
            project_id=data.project_id,
            project_code=resolved_project_code,
            package_id=data.package_id,
            location_code=(data.location_code or "").strip() or None,
        )
        if routed and routed != org_id:
            logger.info(
                "validate_jurisdiction: organization_id %s -> %s (project routing)",
                org_id,
                routed,
            )
            org_id = routed
            data.organization_id = routed
        elif routed:
            data.organization_id = routed

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


def apply_officer_organization(
    db: Session,
    user_id: str,
    organization_id: str,
) -> tuple[int, int]:
    """
    Set organization_id on all user_roles and officer_scopes for an officer.
    Returns (roles_updated, scopes_updated).
    """
    from ticketing.models.officer_scope import OfficerScope
    from ticketing.models.organization import Organization
    from ticketing.models.user import UserRole

    org_id = (organization_id or "").strip()
    if not org_id:
        raise HTTPException(status_code=422, detail="organization_id is required")
    if not db.get(Organization, org_id):
        raise HTTPException(status_code=404, detail=f"Organization {org_id!r} not found")

    roles = db.execute(select(UserRole).where(UserRole.user_id == user_id)).scalars().all()
    scopes = db.execute(select(OfficerScope).where(OfficerScope.user_id == user_id)).scalars().all()
    for row in roles:
        row.organization_id = org_id
    for scope in scopes:
        scope.organization_id = org_id
    return len(roles), len(scopes)


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
    """Best-effort audit row; savepoint so missing table does not roll back caller work."""
    try:
        with db.begin_nested():
            db.add(
                AdminAuditLog(
                    actor_user_id=actor_user_id,
                    action=action,
                    target_user_id=target_user_id,
                    payload=payload,
                )
            )
    except Exception as exc:
        logger.warning("admin_audit_log skipped (%s): %s", action, exc)


def keycloak_configured() -> bool:
    return bool(get_settings().keycloak_admin_url)


def keycloak_invite_preflight() -> dict[str, Any]:
    """
    Read-only readiness check for Keycloak execute-actions invite emails.
    Requires realm SMTP (SMTP_* env + keycloak_setup).
    """
    from ticketing.auth.keycloak_smtp import SMTP_SETUP_HINT, missing_smtp_env_fields

    if not keycloak_configured():
        return {
            "ok": False,
            "configured": False,
            "keycloak_reachable": False,
            "realm": "grm",
            "smtp_configured": False,
            "missing_smtp_fields": ["host", "from", "user", "password"],
            "email_action_supported": False,
            "message": "Keycloak admin settings are not configured.",
        }

    try:
        admin = _keycloak_admin()
        realm_data = admin.connection.raw_get("admin/realms/grm").json()
        smtp = realm_data.get("smtpServer") or {}
    except Exception as exc:
        return {
            "ok": False,
            "configured": True,
            "keycloak_reachable": False,
            "realm": "grm",
            "smtp_configured": False,
            "missing_smtp_fields": ["host", "from", "user", "password"],
            "email_action_supported": False,
            "message": f"Failed to connect to Keycloak realm: {exc}",
        }

    required = ("host", "from", "user", "password")
    missing = [k for k in required if not str(smtp.get(k, "")).strip()]
    smtp_configured = len(missing) == 0
    email_action_supported = hasattr(admin, "send_update_account")
    ok = bool(realm_data.get("enabled", True)) and smtp_configured and email_action_supported

    if not smtp_configured:
        env_missing = missing_smtp_env_fields()
        if env_missing:
            hint = f"Keycloak realm SMTP not configured. Missing env: {', '.join(env_missing)}. {SMTP_SETUP_HINT}"
        else:
            hint = (
                "Keycloak realm SMTP not configured in the grm realm (env looks set — re-run keycloak_setup). "
                + SMTP_SETUP_HINT
            )
    elif ok:
        hint = "Invite email preflight passed (Keycloak execute-actions + realm SMTP)."
    else:
        hint = "Invite email preflight failed. Check Keycloak realm email settings."

    return {
        "ok": ok,
        "configured": True,
        "keycloak_reachable": True,
        "realm": "grm",
        "smtp_configured": smtp_configured,
        "missing_smtp_fields": missing,
        "email_action_supported": email_action_supported,
        "message": hint,
    }


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


def _keycloak_find_user(admin, user_id: str) -> dict | None:
    """Lookup realm user by username or email (case-insensitive email)."""
    uid = user_id.strip()
    for query in (
        {"username": uid, "exact": True},
        {"email": uid, "exact": True},
        {"email": uid.lower(), "exact": True},
    ):
        users = admin.get_users(query=query)
        if users:
            return users[0]
    return None


def _keycloak_invite_email_options() -> tuple[str, str]:
    """client_id + redirect_uri for execute-actions email (Keycloak Admin API)."""
    import os

    settings = get_settings()
    client_id = (
        os.getenv("KEYCLOAK_INVITE_CLIENT_ID") or settings.keycloak_invite_client_id or "ticketing-ui"
    ).strip()
    redirect_uri = (
        os.getenv("KEYCLOAK_INVITE_REDIRECT_URI") or settings.keycloak_invite_redirect_uri or ""
    ).strip()
    if not redirect_uri:
        redirect_uri = "http://localhost:3002/login"
    return client_id, redirect_uri


def _keycloak_send_invite_email(admin, kc_id: str) -> None:
    client_id, redirect_uri = _keycloak_invite_email_options()
    admin.send_update_account(
        user_id=kc_id,
        payload=["UPDATE_PASSWORD", "UPDATE_PROFILE"],
        client_id=client_id,
        redirect_uri=redirect_uri,
    )


def officer_eligible_for_invite_resend(db: Session, email: str) -> bool:
    """True if officer has not finished Keycloak onboarding (invited or pending required actions)."""
    ob = db.get(OfficerOnboarding, email)
    if ob and ob.status == "invited":
        return True
    if not keycloak_configured():
        return False
    kc_user = _keycloak_find_user(_keycloak_admin(), email)
    if not kc_user or not kc_user.get("enabled", True):
        return False
    pending = kc_user.get("requiredActions") or []
    return bool(pending)


def keycloak_resend_invite_email(user_id: str, db=None) -> str:
    """
    Send a fresh execute-actions email (new 7-day link) for an invited officer.
    Returns the normalized email address the message was sent to.
    """
    if not keycloak_configured():
        raise HTTPException(status_code=503, detail="Keycloak is not configured for this environment.")

    preflight = keycloak_invite_preflight()
    if not preflight.get("ok"):
        raise HTTPException(status_code=503, detail=preflight.get("message", "Invite email is not ready."))

    email = user_id.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=422, detail="Resend invite requires an email user id.")

    admin = _keycloak_admin()
    kc_user = _keycloak_find_user(admin, email)
    if not kc_user:
        raise HTTPException(status_code=404, detail="Officer not found in Keycloak.")

    if not kc_user.get("enabled", True):
        raise HTTPException(
            status_code=409,
            detail="Officer account is disabled in Keycloak. Remove and invite again.",
        )

    try:
        admin.update_user(
            user_id=kc_user["id"],
            payload={"requiredActions": ["UPDATE_PASSWORD", "UPDATE_PROFILE"]},
        )
        _keycloak_send_invite_email(admin, kc_user["id"])
    except HTTPException:
        raise
    except Exception as exc:
        err = str(exc)
        if "sender address" in err.lower() or "execute actions email" in err.lower():
            from ticketing.auth.keycloak_smtp import INVITE_EMAIL_FAILURE_HINT

            raise HTTPException(status_code=503, detail=INVITE_EMAIL_FAILURE_HINT)
        raise HTTPException(status_code=500, detail=f"Keycloak error: {err}")

    sent_to = (kc_user.get("email") or email).strip().lower()
    if db is not None:
        from datetime import datetime, timezone

        ob = db.get(OfficerOnboarding, sent_to)
        if ob:
            ob.updated_at = datetime.now(timezone.utc)
    return sent_to


def keycloak_create_user(
    email: str,
    role_key: str,
    organization_id: str,
    temp_password: Optional[str] = None,
) -> None:
    admin = _keycloak_admin()
    local = email.split("@", 1)[0]
    name_parts = local.replace(".", " ").replace("-", " ").split()
    first_name = name_parts[0].title() if name_parts else local
    last_name = name_parts[-1].title() if len(name_parts) > 1 else "Officer"
    create_payload = {
        "username": email,
        "email": email,
        "firstName": first_name,
        "lastName": last_name,
        "enabled": True,
        "emailVerified": False,
        "attributes": {
            "grm_roles": [role_key],
            "organization_id": [organization_id],
        },
        "credentials": [{
            "type": "password",
            "value": temp_password or "GrmDemo2026!",
            "temporary": True,
        }],
        "requiredActions": ["UPDATE_PASSWORD", "UPDATE_PROFILE"],
    }
    try:
        admin.create_user(create_payload)
        kc_user = _keycloak_find_user(admin, email)
        if not kc_user:
            raise HTTPException(
                status_code=500,
                detail=(
                    "Keycloak user was created but could not be reloaded for invite email dispatch."
                ),
            )
        _keycloak_send_invite_email(admin, kc_user["id"])
    except Exception as exc:
        err = str(exc)
        if "409" in err or "already exists" in err.lower():
            existing = _keycloak_find_user(admin, email)
            if existing and existing.get("enabled"):
                raise HTTPException(
                    status_code=409,
                    detail=f"User {email!r} already exists in Keycloak",
                )
            if existing:
                admin.update_user(
                    user_id=existing["id"],
                    payload={
                        "enabled": True,
                        "email": email,
                        "firstName": first_name,
                        "lastName": last_name,
                        "emailVerified": False,
                        "attributes": create_payload["attributes"],
                        "requiredActions": create_payload["requiredActions"],
                        "credentials": create_payload["credentials"],
                    },
                )
                _keycloak_send_invite_email(admin, existing["id"])
                return
            raise HTTPException(
                status_code=409,
                detail=f"User {email!r} already exists in Keycloak",
            )
        if "sender address" in err.lower() or "execute actions email" in err.lower():
            from ticketing.auth.keycloak_smtp import INVITE_EMAIL_FAILURE_HINT

            raise HTTPException(status_code=503, detail=INVITE_EMAIL_FAILURE_HINT)
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
    kc_user = _keycloak_find_user(admin, user_id)
    if not kc_user:
        return
    kc_id = kc_user["id"]
    attrs: dict[str, list[str]] = {
        "grm_roles": [",".join(role_keys) if role_keys else ""],
        "organization_id": [organization_id],
    }
    if location_code:
        attrs["location_code"] = [location_code]
    admin.update_user(user_id=kc_id, payload={"attributes": attrs})


def keycloak_delete_user(user_id: str) -> bool:
    """Remove realm user so roster and re-invite stay consistent. Returns True if deleted."""
    if not keycloak_configured():
        return False
    admin = _keycloak_admin()
    kc_user = _keycloak_find_user(admin, user_id)
    if not kc_user:
        return False
    admin.delete_user(kc_user["id"])
    return True
