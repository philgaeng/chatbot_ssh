"""Project-scoped organization role vocabulary and validation."""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ticketing.models.project import ProjectActorRole
from ticketing.models.settings import Settings

ROLE_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

DEFAULT_ORG_ROLES: list[dict[str, str]] = [
    {"key": "project_owner", "label": "Project Owner", "description": "Government agency that owns and executes the project (e.g. DOR)"},
    {"key": "donor", "label": "Donor / Lender", "description": "Multilateral or bilateral financing institution (e.g. ADB)"},
    {"key": "executing_agency", "label": "Executing Agency", "description": "Central ministry or agency responsible for project oversight"},
    {"key": "implementing_agency", "label": "Implementing Agency", "description": "PD/PIU or other unit responsible for day-to-day implementation"},
    {"key": "main_contractor", "label": "Main Contractor", "description": "Primary civil works contractor"},
    {"key": "subcontractor_t1", "label": "Subcontractor (Tier 1)", "description": "First-tier subcontractor to the main contractor"},
    {"key": "subcontractor_t2", "label": "Subcontractor (Tier 2)", "description": "Second-tier subcontractor"},
    {"key": "supervision_consultant", "label": "CSC – Construction Supervision Consultant", "description": "Independent consultant supervising construction quality"},
    {"key": "specialized_consultant", "label": "Specialized Consultant", "description": "Safeguards, environment, social, or other specialist consultant"},
]


def normalize_role_entry(entry: dict[str, Any], sort_order: int) -> dict[str, str | int]:
    key = (entry.get("key") or "").strip()
    label = (entry.get("label") or "").strip()
    if not key or not label:
        raise ValueError('Each role needs non-empty "key" and "label"')
    if not ROLE_KEY_RE.match(key):
        raise ValueError(f"Invalid role key '{key}' (use lowercase letters, digits, underscores)")
    desc = (entry.get("description") or "").strip()
    return {"role_key": key, "label": label, "description": desc, "sort_order": sort_order}


def load_global_org_roles(db: Session) -> list[dict[str, str]]:
    row = db.get(Settings, "org_roles")
    if row and isinstance(row.value, list) and row.value:
        return row.value
    return DEFAULT_ORG_ROLES


def list_project_actor_roles(db: Session, project_id: str) -> list[ProjectActorRole]:
    return list(
        db.execute(
            select(ProjectActorRole)
            .where(ProjectActorRole.project_id == project_id)
            .order_by(ProjectActorRole.sort_order, ProjectActorRole.role_key)
        ).scalars().all()
    )


def actor_roles_to_api(rows: list[ProjectActorRole]) -> list[dict[str, str | int]]:
    return [
        {
            "key": r.role_key,
            "label": r.label,
            "description": r.description or "",
            "sort_order": r.sort_order,
        }
        for r in rows
    ]


def seed_project_actor_roles(db: Session, project_id: str) -> list[ProjectActorRole]:
    """Copy global org_roles vocabulary into a new project (idempotent)."""
    existing = list_project_actor_roles(db, project_id)
    if existing:
        return existing
    global_roles = load_global_org_roles(db)
    created: list[ProjectActorRole] = []
    for i, entry in enumerate(global_roles):
        norm = normalize_role_entry(entry, i)
        row = ProjectActorRole(
            project_id=project_id,
            role_key=norm["role_key"],
            label=norm["label"],
            description=norm["description"] or None,
            sort_order=norm["sort_order"],
        )
        db.add(row)
        created.append(row)
    db.flush()
    return created


def project_role_keys(db: Session, project_id: str) -> set[str]:
    rows = list_project_actor_roles(db, project_id)
    if not rows:
        seed_project_actor_roles(db, project_id)
        rows = list_project_actor_roles(db, project_id)
    return {r.role_key for r in rows}


def validate_org_role_for_project(db: Session, project_id: str, org_role: str | None) -> None:
    if org_role is None:
        return
    keys = project_role_keys(db, project_id)
    if org_role not in keys:
        raise ValueError(f"Unknown role '{org_role}' for this project")


def replace_project_actor_roles(db: Session, project_id: str, roles: list[dict[str, Any]]) -> list[ProjectActorRole]:
    if not roles:
        raise ValueError("At least one actor role is required per project")
    seen: set[str] = set()
    normalized: list[dict[str, str | int]] = []
    for i, entry in enumerate(roles):
        norm = normalize_role_entry(entry, i)
        key = str(norm["role_key"])
        if key in seen:
            raise ValueError(f"Duplicate role key '{key}'")
        seen.add(key)
        normalized.append(norm)

    from ticketing.models.package import PackageOrganization, ProjectPackage
    from ticketing.models.project import ProjectOrganization

    in_use_project = {
        r
        for r in db.execute(
            select(ProjectOrganization.org_role).where(
                ProjectOrganization.project_id == project_id,
                ProjectOrganization.org_role.isnot(None),
            )
        ).scalars().all()
        if r
    }
    in_use_package = {
        r
        for r in db.execute(
            select(PackageOrganization.org_role)
            .join(ProjectPackage, ProjectPackage.package_id == PackageOrganization.package_id)
            .where(ProjectPackage.project_id == project_id)
        ).scalars().all()
        if r
    }
    removed = (in_use_project | in_use_package) - seen
    if removed:
        raise ValueError(
            f"Cannot remove role(s) still assigned to actors: {', '.join(sorted(removed))}"
        )

    db.execute(
        ProjectActorRole.__table__.delete().where(ProjectActorRole.project_id == project_id)
    )
    created: list[ProjectActorRole] = []
    for norm in normalized:
        row = ProjectActorRole(
            project_id=project_id,
            role_key=str(norm["role_key"]),
            label=str(norm["label"]),
            description=str(norm["description"]) or None,
            sort_order=int(norm["sort_order"]),
        )
        db.add(row)
        created.append(row)
    db.flush()
    return created
