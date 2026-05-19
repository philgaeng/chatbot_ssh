"""Officer self-service profile — stored in Keycloak (not ticketing.* PII tables)."""
from __future__ import annotations

import re
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ticketing.constants.grm_role_catalog import GRM_ROLE_CATALOG
from ticketing.models.user import Role, UserRole
from ticketing.services.keycloak_users import keycloak_configured
from ticketing.services.officer_admin import _keycloak_admin

_PHONE_RE = re.compile(r"^\+?[0-9][0-9\s\-()]{7,18}$")


class OfficerProfileResponse(BaseModel):
    user_id: str
    email: str
    first_name: str
    last_name: str
    phone_number: str
    job_title: str
    role_keys: list[str]
    role_labels: list[str]


class OfficerProfilePatch(BaseModel):
    first_name: str = Field(min_length=1, max_length=64)
    last_name: str = Field(min_length=1, max_length=64)
    phone_number: str = Field(min_length=8, max_length=20)
    job_title: str = Field(default="", max_length=120)


def _role_labels(role_keys: list[str]) -> list[str]:
    by_key = {r["role_key"]: r["display_name"] for r in GRM_ROLE_CATALOG}
    return [by_key.get(k, k) for k in role_keys]


def _db_role_keys(db: Session, user_id: str) -> list[str]:
    rows = db.execute(
        select(Role.role_key)
        .join(UserRole, UserRole.role_id == Role.role_id)
        .where(UserRole.user_id == user_id)
        .order_by(Role.role_key)
    ).scalars().all()
    return list(dict.fromkeys(rows))


def _find_kc_user(admin, user_id: str) -> dict | None:
    for query in ({"username": user_id, "exact": True}, {"email": user_id, "exact": True}):
        found = admin.get_users(query)
        if found:
            return admin.get_user(found[0]["id"])
    return None


def _attrs(user: dict) -> dict[str, list[str]]:
    return user.get("attributes") or {}


def get_officer_profile(db: Session, user_id: str) -> OfficerProfileResponse:
    role_keys = _db_role_keys(db, user_id)
    email = user_id if "@" in user_id else user_id
    first_name = ""
    last_name = ""
    phone_number = ""
    job_title = ""

    if keycloak_configured():
        admin = _keycloak_admin()
        kc = _find_kc_user(admin, user_id)
        if kc:
            email = (kc.get("email") or kc.get("username") or email).strip()
            first_name = (kc.get("firstName") or "").strip()
            last_name = (kc.get("lastName") or "").strip()
            attrs = _attrs(kc)
            phone_number = (attrs.get("phone_number") or [""])[0].strip()
            job_title = (attrs.get("job_title") or [""])[0].strip()

    if not first_name and not last_name and "@" in email:
        local = email.split("@", 1)[0].replace(".", " ").replace("-", " ")
        parts = local.split()
        first_name = parts[0].title() if parts else email
        last_name = parts[-1].title() if len(parts) > 1 else ""

    return OfficerProfileResponse(
        user_id=user_id,
        email=email,
        first_name=first_name,
        last_name=last_name,
        phone_number=phone_number,
        job_title=job_title,
        role_keys=role_keys,
        role_labels=_role_labels(role_keys),
    )


def update_officer_profile(
    db: Session,
    user_id: str,
    patch: OfficerProfilePatch,
) -> OfficerProfileResponse:
    phone = patch.phone_number.strip()
    if not _PHONE_RE.match(phone):
        raise HTTPException(
            status_code=422,
            detail="Enter a valid phone number (digits, optional + prefix).",
        )

    if not keycloak_configured():
        raise HTTPException(
            status_code=503,
            detail="Profile editing requires Keycloak (auth stack).",
        )

    admin = _keycloak_admin()
    kc = _find_kc_user(admin, user_id)
    if not kc:
        raise HTTPException(status_code=404, detail="Keycloak user not found")

    attrs = _attrs(kc)
    attrs["phone_number"] = [phone]
    attrs["job_title"] = [patch.job_title.strip()]

    admin.update_user(
        user_id=kc["id"],
        payload={
            "firstName": patch.first_name.strip(),
            "lastName": patch.last_name.strip(),
            "email": kc.get("email") or user_id,
            "attributes": attrs,
        },
    )

    return get_officer_profile(db, user_id)
