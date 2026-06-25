"""
Officer admin helpers: jurisdiction validation, Keycloak sync, audit logging.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Keycloak execute-actions on invite — password only; profile fields live in GRM Account settings.
KEYCLOAK_ONBOARDING_ACTIONS = ["UPDATE_PASSWORD"]

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ticketing.config.settings import get_settings
from ticketing.models.admin_audit_log import AdminAuditLog
from ticketing.models.officer_onboarding import OfficerOnboarding
from ticketing.models.officer_scope import OfficerScope
from ticketing.models.package import ProjectPackage
from ticketing.models.project import Project
from ticketing.models.user import Role, UserRole
from ticketing.services.officer_jurisdiction import scope_requires_field_jurisdiction
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

    # organization_id is the officer's employer (contractor, CSC, etc.) — not rewritten
    # to the project implementing agency; auto-assign matches role + package/project only.
    data.organization_id = org_id

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


def _names_from_email(email: str) -> tuple[str, str]:
    local = email.split("@", 1)[0]
    name_parts = local.replace(".", " ").replace("-", " ").split()
    first = name_parts[0].title() if name_parts else local
    last = name_parts[-1].title() if len(name_parts) > 1 else "Officer"
    return first, last


def _ensure_keycloak_user_email(admin, kc_user: dict, fallback_email: str) -> dict:
    """
    Keycloak execute-actions email fails with 'User email missing' when the email
    field is empty (username may still hold the address).
    """
    current = (kc_user.get("email") or "").strip()
    if current and "@" in current:
        return kc_user

    repair = _normalize_officer_email(fallback_email)
    if not repair or "@" not in repair:
        username = (kc_user.get("username") or "").strip()
        if "@" in username:
            repair = username.lower()

    if not repair or "@" not in repair:
        raise HTTPException(
            status_code=422,
            detail="This officer account has no email in Keycloak. Set a valid email before resending invite.",
        )

    first, last = _names_from_email(repair)
    payload: dict[str, Any] = {
        "email": repair,
        "emailVerified": False,
    }
    if not (kc_user.get("firstName") or "").strip():
        payload["firstName"] = first
    if not (kc_user.get("lastName") or "").strip():
        payload["lastName"] = last
    if not (kc_user.get("username") or "").strip():
        payload["username"] = repair

    admin.update_user(user_id=kc_user["id"], payload=payload)
    refreshed = admin.get_user(kc_user["id"])
    return refreshed if refreshed else {**kc_user, **payload}


def _keycloak_send_invite_email(admin, kc_user: dict, fallback_email: str) -> None:
    kc_user = _ensure_keycloak_user_email(admin, kc_user, fallback_email)
    client_id, redirect_uri = _keycloak_invite_email_options()
    admin.send_update_account(
        user_id=kc_user["id"],
        payload=list(KEYCLOAK_ONBOARDING_ACTIONS),
        client_id=client_id,
        redirect_uri=redirect_uri,
    )


def _normalize_officer_email(email: str) -> str:
    return email.strip().lower()


def _officer_role_keys(db: Session, email: str) -> list[str]:
    """Effective role keys for Keycloak sync (user_roles + scopes + admin_scopes)."""
    from ticketing.services.admin_access import load_effective_role_keys

    return load_effective_role_keys(db, _normalize_officer_email(email))


def sync_officer_keycloak_roles(db: Session, email: str) -> None:
    """Push effective DB role keys to Keycloak grm_roles attribute."""
    if not keycloak_configured():
        return
    normalized = _normalize_officer_email(email)
    role_keys = _officer_role_keys(db, normalized)
    if not role_keys:
        return
    org_id = _primary_officer_organization(db, normalized)
    keycloak_update_user_attributes(normalized, role_keys, org_id)


def _primary_officer_organization(db: Session, email: str) -> str:
    normalized = _normalize_officer_email(email)
    org_id = db.execute(
        select(UserRole.organization_id)
        .where(func.lower(UserRole.user_id) == normalized)
        .limit(1)
    ).scalar_one_or_none()
    return (org_id or "DOR").strip() or "DOR"


def _upsert_officer_onboarding(db: Session, email: str, status: str) -> None:
    from datetime import datetime, timezone

    normalized = _normalize_officer_email(email)
    ob = db.get(OfficerOnboarding, normalized)
    if ob:
        ob.status = status
        ob.updated_at = datetime.now(timezone.utc)
    else:
        db.add(OfficerOnboarding(user_id=normalized, status=status))


def keycloak_onboarding_complete(email: str) -> bool:
    """True when Keycloak user is enabled with no pending password setup."""
    if not keycloak_configured():
        return True
    return not officer_invite_setup_pending(None, email)


def officer_invite_setup_pending(db: Session | None, email: str) -> bool:
    """
    True when the officer has not finished Keycloak password setup.

    Used for roster Invited badge — prefers Keycloak state over stale DB rows
    (migration backfill marked existing user_roles as active).
    """
    normalized = _normalize_officer_email(email)
    if not keycloak_configured():
        if db is None:
            return False
        ob = db.get(OfficerOnboarding, normalized)
        return bool(ob and ob.status == "invited")

    kc_user = _keycloak_find_user(_keycloak_admin(), normalized)
    if not kc_user:
        return True
    if not kc_user.get("enabled", True):
        return True
    pending = kc_user.get("requiredActions") or []
    if pending:
        return True
    if not kc_user.get("emailVerified", False):
        return True
    return False


def officer_roster_onboarding_status(db: Session, uid: str) -> str:
    """Display status for Settings → Officers roster."""
    if officer_invite_setup_pending(db, uid):
        return "invited"
    return "active"


def activate_officer_onboarding(db: Session, email: str) -> bool:
    """Set officer_onboarding to active. Returns True when a row was created or updated."""
    from datetime import datetime, timezone

    normalized = _normalize_officer_email(email)
    row = db.get(OfficerOnboarding, normalized)
    now = datetime.now(timezone.utc)
    if row:
        if row.status == "active":
            return False
        row.status = "active"
        row.updated_at = now
        return True
    db.add(OfficerOnboarding(user_id=normalized, status="active", updated_at=now))
    return True


def sync_officer_onboarding_status(db: Session, email: str) -> bool:
    """
    Promote invited → active when Keycloak onboarding is complete.

    Fallback when the Keycloak event webhook is unavailable. Returns True if DB changed.
    """
    normalized = _normalize_officer_email(email)
    ob = db.get(OfficerOnboarding, normalized)
    if ob and ob.status == "active":
        return False
    if not keycloak_onboarding_complete(normalized):
        return False
    return activate_officer_onboarding(db, normalized)


def officer_eligible_for_invite_resend(db: Session, email: str) -> bool:
    """True if officer can receive a fresh Keycloak setup (execute-actions) email."""
    return officer_invite_setup_pending(db, email)


def admin_scope_can_send_setup_email() -> bool:
    """Admin access rows may trigger Keycloak setup email when auth stack is configured."""
    return keycloak_configured()


def _keycloak_send_or_create_setup_email(
    db: Session,
    email: str,
    role_key: str,
    organization_id: str,
) -> None:
    """Create Keycloak user if missing, then send execute-actions setup email."""
    normalized = _normalize_officer_email(email)
    org_id = organization_id.strip() or "DOR"
    admin = _keycloak_admin()
    kc_user = _keycloak_find_user(admin, normalized)
    if not kc_user:
        keycloak_create_user(normalized, role_key, org_id)
        _upsert_officer_onboarding(db, normalized, "invited")
        return

    role_keys = _officer_role_keys(db, normalized) or [role_key]
    keycloak_update_user_attributes(normalized, role_keys, org_id)
    if not kc_user.get("enabled", True):
        admin.update_user(user_id=kc_user["id"], payload={"enabled": True})
    keycloak_resend_invite_email(normalized, db=db)


def provision_admin_scope_keycloak(
    db: Session,
    email: str,
    role_key: str,
    organization_id: str,
    *,
    force_invite: bool = False,
) -> str:
    """
    Ensure Keycloak account exists for an admin-scope appointee and send invite when needed.
    Returns officer_onboarding status: invited | active
    """
    normalized = _normalize_officer_email(email)
    if "@" not in normalized:
        raise HTTPException(status_code=422, detail="Admin appoint requires an email user id.")

    if not keycloak_configured():
        _upsert_officer_onboarding(db, normalized, "active")
        return "active"

    org_id = organization_id.strip() or "DOR"
    if force_invite or officer_eligible_for_invite_resend(db, normalized):
        _keycloak_send_or_create_setup_email(db, normalized, role_key, org_id)
        return "invited"

    role_keys = _officer_role_keys(db, normalized) or [role_key]
    keycloak_update_user_attributes(normalized, role_keys, org_id)
    _upsert_officer_onboarding(db, normalized, "active")
    return "active"


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
        if db is None:
            raise HTTPException(status_code=404, detail="Officer not found in Keycloak.")
        role_keys = _officer_role_keys(db, email)
        if not role_keys:
            raise HTTPException(status_code=404, detail="Officer not found in Keycloak.")
        keycloak_create_user(email, role_keys[0], _primary_officer_organization(db, email))
        _upsert_officer_onboarding(db, email, "invited")
        return email

    if not kc_user.get("enabled", True):
        admin.update_user(user_id=kc_user["id"], payload={"enabled": True})

    try:
        admin.update_user(
            user_id=kc_user["id"],
            payload={"requiredActions": list(KEYCLOAK_ONBOARDING_ACTIONS)},
        )
        _keycloak_send_invite_email(admin, kc_user, email)
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
        _upsert_officer_onboarding(db, sent_to, "invited")
    return sent_to


def keycloak_create_user(
    email: str,
    role_key: str,
    organization_id: str,
    temp_password: Optional[str] = None,
) -> None:
    admin = _keycloak_admin()
    first_name, last_name = _names_from_email(email)
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
            "phone_number": ["9800000000"],
        },
        "credentials": [{
            "type": "password",
            "value": temp_password or "GrmDemo2026!",
            "temporary": True,
        }],
        "requiredActions": list(KEYCLOAK_ONBOARDING_ACTIONS),
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
        _keycloak_send_invite_email(admin, kc_user, email)
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
                _keycloak_send_invite_email(admin, existing, email)
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
