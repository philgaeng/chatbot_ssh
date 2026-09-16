# SPDX-License-Identifier: Apache-2.0

"""Project archetype (project_types) — instantiate and validate."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ticketing.models.project import Project
from ticketing.models.project_type import ProjectType


def get_project_type(db: Session, type_key: str) -> ProjectType | None:
    return db.get(ProjectType, type_key)


def list_project_types(
    db: Session,
    active_only: bool = True,
    *,
    user=None,
    owner_organization_id: str | None = None,
) -> list[ProjectType]:
    """Project types, newest catalog rules applied.

    ``user`` narrows the list to what that admin may see — global types (owner NULL) plus
    those owned inside its own subtree (DECISION-author-defined-slots §3.1). ``owner_organization_id``
    narrows further to the types offered *for one organization*: its own plus the global ones.
    """
    stmt = select(ProjectType).order_by(ProjectType.sort_order, ProjectType.type_key)
    if active_only:
        stmt = stmt.where(ProjectType.is_active.is_(True))
    if owner_organization_id:
        from ticketing.services.org_tree import ancestor_org_ids

        # A type authored at an organization is available there **and below it** (doc 11 §3.3),
        # so a district office can be created from its ministry's template.
        offered = ancestor_org_ids(db, owner_organization_id, include_self=True)
        stmt = stmt.where(
            (ProjectType.owner_organization_id.in_(offered))
            | (ProjectType.owner_organization_id.is_(None))
        )
    if user is not None:
        from ticketing.services.admin_access import apply_catalog_scope

        stmt = apply_catalog_scope(stmt, db, user, ProjectType.owner_organization_id)
    return list(db.execute(stmt).scalars().all())


def instantiate_project_from_type(db: Session, project: Project, type_key: str) -> ProjectType:
    """Apply the type's workflows to a new project. Its organization catalog stays on the type."""
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
                    "intake_route": "new_grievance",
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
                    "intake_route": "seah_intake",
                    "sort_order": 30,
                }
            )
        if legacy_bindings:
            pw_svc.apply_workflow_bindings_from_type(db, project, legacy_bindings)

    # The organization catalog is NOT copied into the project (DECISION-author-defined-slots
    # §3.3): it is read from the type, one catalog per archetype. Copying it per project is how
    # a vocabulary drifts — `project_actor_roles` stays dead for typed projects.
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
