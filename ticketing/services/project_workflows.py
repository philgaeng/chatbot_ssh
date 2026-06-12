"""CRUD for ticketing.project_workflows."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ticketing.models.project import Project
from ticketing.models.project_workflow import ProjectWorkflow
from ticketing.models.workflow import WorkflowDefinition


def _new_id() -> str:
    return str(uuid.uuid4())


def list_project_workflows(db: Session, project_id: str) -> list[ProjectWorkflow]:
    return list(
        db.execute(
            select(ProjectWorkflow)
            .where(ProjectWorkflow.project_id == project_id)
            .order_by(ProjectWorkflow.sort_order, ProjectWorkflow.display_label)
        ).scalars().all()
    )


def validate_workflow_binding(db: Session, workflow_id: str) -> WorkflowDefinition:
    wf = db.get(WorkflowDefinition, workflow_id)
    if not wf:
        raise HTTPException(status_code=422, detail=f"Workflow '{workflow_id}' not found")
    if wf.is_template:
        raise HTTPException(status_code=422, detail="Templates cannot be assigned to a project")
    if wf.status != "published":
        raise HTTPException(status_code=422, detail="Only published workflows can be assigned to a project")
    return wf


def _sync_legacy_columns(project: Project, links: list[ProjectWorkflow], db: Session) -> None:
    project.standard_workflow_id = None
    project.seah_workflow_id = None
    default_wf: str | None = None
    for link in links:
        if link.is_default:
            default_wf = link.workflow_id
            break
    if default_wf:
        project.standard_workflow_id = default_wf
    for link in links:
        wf = db.get(WorkflowDefinition, link.workflow_id)
        if wf and (wf.workflow_type or "").lower() == "seah":
            project.seah_workflow_id = link.workflow_id
            break


def _normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    label = str(item.get("display_label") or "").strip()
    if not label:
        raise HTTPException(status_code=422, detail="display_label is required")
    wf_id = str(item["workflow_id"])
    return {
        "display_label": label,
        "workflow_id": wf_id,
        "classifications": list(item.get("classifications") or []),
        "intake_routes": list(item.get("intake_routes") or []),
        "is_default": bool(item.get("is_default")),
        "sort_order": int(item.get("sort_order") or 0),
    }


def replace_project_workflows(
    db: Session,
    project: Project,
    items: list[dict[str, Any]],
) -> list[ProjectWorkflow]:
    """Replace all workflow bindings for a project (PUT semantics)."""
    if not items:
        raise HTTPException(status_code=422, detail="At least one workflow binding is required")
    defaults = sum(1 for item in items if item.get("is_default"))
    if defaults != 1:
        raise HTTPException(status_code=422, detail="Exactly one workflow binding must be marked is_default")

    normalized = [_normalize_item(item) for item in items]
    for n in normalized:
        validate_workflow_binding(db, n["workflow_id"])

    for row in list_project_workflows(db, project.project_id):
        db.delete(row)
    db.flush()

    out: list[ProjectWorkflow] = []
    for i, n in enumerate(normalized):
        row = ProjectWorkflow(
            project_workflow_id=_new_id(),
            project_id=project.project_id,
            workflow_id=n["workflow_id"],
            display_label=n["display_label"],
            classifications=n["classifications"],
            intake_routes=n["intake_routes"],
            is_default=n["is_default"],
            sort_order=n["sort_order"] if n["sort_order"] else (i + 1) * 10,
        )
        db.add(row)
        out.append(row)

    db.flush()
    _sync_legacy_columns(project, out, db)
    return out


def apply_workflow_bindings_from_type(
    db: Session,
    project: Project,
    bindings: list[dict[str, Any]],
) -> list[ProjectWorkflow]:
    """Instantiate project workflows from project_types.workflow_bindings."""
    if not bindings:
        return []
    return replace_project_workflows(db, project, bindings)


def project_workflow_to_dict(row: ProjectWorkflow, db: Session | None = None) -> dict[str, Any]:
    wf_type = "standard"
    if db is not None:
        wf = db.get(WorkflowDefinition, row.workflow_id)
        if wf:
            wf_type = wf.workflow_type or "standard"
    return {
        "project_workflow_id": row.project_workflow_id,
        "project_id": row.project_id,
        "workflow_id": row.workflow_id,
        "display_label": row.display_label,
        "classifications": row.classifications or [],
        "intake_routes": row.intake_routes or [],
        "is_default": row.is_default,
        "workflow_track": wf_type,
        "sort_order": row.sort_order,
    }
