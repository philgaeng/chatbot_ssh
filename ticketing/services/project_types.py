"""Project archetype (project_types) — instantiate and validate."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ticketing.models.project import Project, ProjectActorRole
from ticketing.models.project_type import ProjectType
from ticketing.services import project_actor_roles as actor_roles_svc


def get_project_type(db: Session, type_key: str) -> ProjectType | None:
    return db.get(ProjectType, type_key)


def list_project_types(db: Session, active_only: bool = True) -> list[ProjectType]:
    stmt = select(ProjectType).order_by(ProjectType.sort_order, ProjectType.type_key)
    if active_only:
        stmt = stmt.where(ProjectType.is_active.is_(True))
    return list(db.execute(stmt).scalars().all())


def type_actor_roles_for_project_seed(type_row: ProjectType) -> list[dict[str, Any]]:
    """Unique role keys for project_actor_roles table."""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for i, entry in enumerate(type_row.actor_roles or []):
        key = (entry.get("key") or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "key": key,
                "label": entry.get("label") or key,
                "description": entry.get("description") or "",
                "sort_order": i,
            }
        )
    return out


def instantiate_project_from_type(db: Session, project: Project, type_key: str) -> ProjectType:
    """Apply archetype workflows and actor vocabulary to a new project."""
    pt = get_project_type(db, type_key)
    if not pt or not pt.is_active:
        raise ValueError(f"Unknown or inactive project type '{type_key}'")

    project.project_type_key = type_key
    project.standard_workflow_id = pt.standard_workflow_id
    project.seah_workflow_id = pt.seah_workflow_id

    from ticketing.services import project_workflows as pw_svc

    bindings = list(pt.workflow_bindings or [])
    if bindings:
        pw_svc.apply_workflow_bindings_from_type(db, project, bindings)
    else:
        legacy_bindings: list[dict] = []
        if pt.standard_workflow_id:
            legacy_bindings.append(
                {
                    "display_label": "Safeguards GRM",
                    "workflow_id": pt.standard_workflow_id,
                    "is_default": True,
                    "classifications": [],
                    "intake_routes": ["standard_grievance", "grievance_new", "new_grievance"],
                    "sort_order": 10,
                }
            )
        if pt.seah_workflow_id:
            legacy_bindings.append(
                {
                    "display_label": "SEAH",
                    "workflow_id": pt.seah_workflow_id,
                    "is_default": False,
                    "classifications": [
                        "Gender",
                        "Gender, Social",
                        "Malicious Behavior",
                        "Malicious Behavior, Environmental",
                    ],
                    "intake_routes": ["seah_intake"],
                    "sort_order": 30,
                }
            )
        if legacy_bindings:
            pw_svc.apply_workflow_bindings_from_type(db, project, legacy_bindings)

    roles_payload = type_actor_roles_for_project_seed(pt)
    if roles_payload:
        actor_roles_svc.replace_project_actor_roles(db, project.project_id, roles_payload)

    return pt


def required_project_role_keys(type_row: ProjectType) -> set[str]:
    keys: set[str] = set()
    for entry in type_row.actor_roles or []:
        if entry.get("required"):
            keys.add(str(entry["key"]))
    return keys


def package_required_role_keys(type_row: ProjectType) -> set[str]:
    keys: set[str] = set()
    for entry in type_row.actor_roles or []:
        if entry.get("required_package"):
            keys.add(str(entry["key"]))
    return keys
