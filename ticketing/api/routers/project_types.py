"""Project archetypes — super_admin CRUD; all admins can list for project create."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from sqlalchemy import func, select

from ticketing.api.dependencies import CurrentUser, require_admin, require_super_admin
from ticketing.models.base import get_db
from ticketing.models.project_type import ProjectType
from ticketing.services import project_types as types_svc

router = APIRouter()
UTC = timezone.utc


def _now() -> datetime:
    return datetime.now(UTC)


class TypeActorRoleItem(BaseModel):
    key: str
    label: str
    description: str = ""
    required: bool = False
    required_package: bool = False
    scope: str = "project"


class ProjectTypeResponse(BaseModel):
    type_key: str
    owner_organization_id: str | None = None
    #: Projects **accepting grievances** on this type. >0 means its setup is frozen (§8) — the
    #: UI shows "Use as template" (or "deactivate first") instead of an edit form. Name and
    #: description stay editable either way.
    active_project_count: int = 0
    label: str
    description: str | None
    standard_workflow_id: str | None
    seah_workflow_id: str | None
    routing_org_role: str
    actor_roles: list[dict[str, Any]]
    is_active: bool
    sort_order: int

    model_config = {"from_attributes": True}


class ProjectTypeDuplicate(BaseModel):
    type_key: str = Field(..., max_length=64, pattern=r"^[a-z][a-z0-9_]{0,63}$")
    label: str | None = None
    owner_organization_id: str | None = None


class ProjectTypeCreate(BaseModel):
    type_key: str = Field(..., max_length=64, pattern=r"^[a-z][a-z0-9_]{0,63}$")
    label: str
    description: str | None = None
    standard_workflow_id: str | None = None
    seah_workflow_id: str | None = None
    routing_org_role: str = "implementing_agency"
    actor_roles: list[TypeActorRoleItem] = []
    is_active: bool = True
    sort_order: int = 0


class ProjectTypeUpdate(BaseModel):
    label: str | None = None
    description: str | None = None
    standard_workflow_id: str | None = None
    seah_workflow_id: str | None = None
    routing_org_role: str | None = None
    actor_roles: list[TypeActorRoleItem] | None = None
    is_active: bool | None = None
    sort_order: int | None = None


def _to_response(row: ProjectType, *, bound: int = 0) -> ProjectTypeResponse:
    return ProjectTypeResponse(
        type_key=row.type_key,
        owner_organization_id=row.owner_organization_id,
        active_project_count=bound,
        label=row.label,
        description=row.description,
        standard_workflow_id=row.standard_workflow_id,
        seah_workflow_id=row.seah_workflow_id,
        routing_org_role=row.routing_org_role,
        actor_roles=row.actor_roles or [],
        is_active=row.is_active,
        sort_order=row.sort_order,
    )


#: Fields that describe HOW a project is configured. Frozen while the type has a LIVE project
#: (DECISION-author-defined-slots §8, amended 2026-08-04).
#:
#: Deliberately NOT here:
#:   • `label` / `description` — a name is not configuration. Renaming a type changes nothing
#:     about what any project runs, and the migration that back-fills types names them "Type 1",
#:     "Type 2", which somebody must be able to fix.
#:   • `is_active` / `sort_order` — availability. Retiring a type from the New-project list
#:     changes nothing about the projects already running on it.
CONFIG_FIELDS = (
    "standard_workflow_id",
    "seah_workflow_id",
    "routing_org_role",
    "actor_roles",
    "workflow_bindings",
    "owner_organization_id",
)


def _active_project_count(db: Session, type_key: str) -> int:
    """Projects **accepting grievances** on this type.

    The freeze protects live work, so it counts active projects only (amended 2026-08-04). A
    project that is not active has no officers depending on its setup, which makes
    *deactivate → fix the type → reactivate* the supported repair path — and reactivating means
    passing go-live again, so a broken setup cannot sneak back.
    """
    from ticketing.models.project import Project

    return int(
        db.execute(
            select(func.count())
            .select_from(Project)
            .where(Project.project_type_key == type_key, Project.is_active.is_(True))
        ).scalar_one()
    )


def _active_counts(db: Session) -> dict[str, int]:
    """type_key → active-project count, in one query (the list endpoint needs every type)."""
    from ticketing.models.project import Project

    rows = db.execute(
        select(Project.project_type_key, func.count())
        .where(Project.project_type_key.isnot(None), Project.is_active.is_(True))
        .group_by(Project.project_type_key)
    ).all()
    return {k: int(n) for k, n in rows}


def _require_editable(db: Session, type_key: str, fields: set[str]) -> None:
    """A type with a live project cannot be re-configured (§8).

    Enforced here rather than by disabling the form: a disabled form is a suggestion, and this
    is the rule that stops one edit from re-configuring every project of a kind at once.
    """
    if not (fields & set(CONFIG_FIELDS)):
        return
    n = _active_project_count(db, type_key)
    if n:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{n} active project{'s use' if n != 1 else ' uses'} this type, so its setup "
                "cannot change. Deactivate the project first, or use this type as a template "
                "to make an edited copy."
            ),
        )


@router.get("/project-types", response_model=list[ProjectTypeResponse])
def list_project_types(
    active_only: bool = True,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_admin),
):
    rows = types_svc.list_project_types(db, active_only=active_only)
    counts = _active_counts(db)
    return [_to_response(r, bound=counts.get(r.type_key, 0)) for r in rows]


@router.get("/project-types/{type_key}", response_model=ProjectTypeResponse)
def get_project_type(
    type_key: str,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_admin),
):
    row = types_svc.get_project_type(db, type_key)
    if not row:
        raise HTTPException(status_code=404, detail="Project type not found")
    return _to_response(row, bound=_active_project_count(db, type_key))


@router.post("/project-types", response_model=ProjectTypeResponse, status_code=201)
def create_project_type(
    body: ProjectTypeCreate,
    db: Session = Depends(get_db),
    _admin: CurrentUser = Depends(require_super_admin),
):
    if types_svc.get_project_type(db, body.type_key):
        raise HTTPException(status_code=409, detail=f"Project type '{body.type_key}' already exists")
    now = _now()
    row = ProjectType(
        type_key=body.type_key,
        label=body.label,
        description=body.description,
        standard_workflow_id=body.standard_workflow_id,
        seah_workflow_id=body.seah_workflow_id,
        routing_org_role=body.routing_org_role,
        actor_roles=[r.model_dump() for r in body.actor_roles],
        is_active=body.is_active,
        sort_order=body.sort_order,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_response(row)


@router.patch("/project-types/{type_key}", response_model=ProjectTypeResponse)
def update_project_type(
    type_key: str,
    body: ProjectTypeUpdate,
    db: Session = Depends(get_db),
    _admin: CurrentUser = Depends(require_super_admin),
):
    row = types_svc.get_project_type(db, type_key)
    if not row:
        raise HTTPException(status_code=404, detail="Project type not found")
    _require_editable(db, type_key, body.model_fields_set)
    if body.label is not None:
        row.label = body.label
    if body.description is not None:
        row.description = body.description
    if body.standard_workflow_id is not None:
        row.standard_workflow_id = body.standard_workflow_id
    if body.seah_workflow_id is not None:
        row.seah_workflow_id = body.seah_workflow_id
    if body.routing_org_role is not None:
        row.routing_org_role = body.routing_org_role
    if body.actor_roles is not None:
        row.actor_roles = [r.model_dump() for r in body.actor_roles]
    if body.is_active is not None:
        row.is_active = body.is_active
    if body.sort_order is not None:
        row.sort_order = body.sort_order
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return _to_response(row, bound=_active_project_count(db, type_key))


@router.post(
    "/project-types/{type_key}/duplicate",
    response_model=ProjectTypeResponse,
    status_code=201,
    summary="Use as template — copy a type so it can be edited (§8: a type in use is frozen)",
)
def duplicate_project_type(
    type_key: str,
    body: ProjectTypeDuplicate,
    db: Session = Depends(get_db),
    _admin: CurrentUser = Depends(require_super_admin),
):
    src = types_svc.get_project_type(db, type_key)
    if not src:
        raise HTTPException(status_code=404, detail="Project type not found")
    if types_svc.get_project_type(db, body.type_key):
        raise HTTPException(status_code=409, detail=f"Project type '{body.type_key}' already exists")
    now = _now()
    row = ProjectType(
        type_key=body.type_key,
        label=body.label or f"{src.label} (copy)",
        description=src.description,
        standard_workflow_id=src.standard_workflow_id,
        seah_workflow_id=src.seah_workflow_id,
        routing_org_role=src.routing_org_role,
        actor_roles=list(src.actor_roles or []),
        workflow_bindings=list(src.workflow_bindings or []),
        owner_organization_id=body.owner_organization_id or src.owner_organization_id,
        # A copy starts unavailable: it is not offered for new projects until its author
        # has finished editing and turns it on.
        is_active=False,
        sort_order=src.sort_order,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_response(row)
