"""Project types — the template a project is built from (DECISION-author-defined-slots).

A type binds the workflows a project runs and names the organizations it must have
(``actor_roles``). Spec: doc 14 §4, doc 13 §3.

It no longer designates *one* of those organizations as the grievance's owner: the
``routing_org_role`` anchor was retired 2026-08-04 (DECISION-organization-membership) because
reporting is **membership** — every organization named on a project sees its grievances. The
column survives, unused, until a cleanup migration drops it.

Authoring is an **org-scoped catalog**, like workflows and position types: ``super_admin``
authors anywhere, an ``org_admin`` within its own subtree (§3.1). A type with a live project
is **frozen** — see ``CONFIG_FIELDS`` and ``_require_editable``.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from sqlalchemy import func, select

from ticketing.api.dependencies import CurrentUser, require_admin
from ticketing.models.base import get_db
from ticketing.models.organization import Organization
from ticketing.models.project_type import ProjectType
from ticketing.services import project_types as types_svc
from ticketing.services.admin_access import (
    admin_org_scope_ids,
    apply_catalog_scope,
    catalog_owner_for,
    is_org_admin,
    is_super_admin,
)
from ticketing.services.project_actor_roles import ROLE_KEY_RE

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


class TypeWorkflowBindingItem(BaseModel):
    """One workflow a project of this type runs — the same shape the project screen edits."""

    display_label: str = Field(..., max_length=200)
    workflow_id: str = Field(..., max_length=36)
    is_default: bool = False
    classifications: list[str] = []
    intake_route: str | None = None
    sort_order: int = 0


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
    actor_roles: list[dict[str, Any]]
    workflow_bindings: list[dict[str, Any]]
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
    actor_roles: list[TypeActorRoleItem] = []
    workflow_bindings: list[TypeWorkflowBindingItem] = []
    owner_organization_id: str | None = None
    is_active: bool = True
    sort_order: int = 0


class ProjectTypeUpdate(BaseModel):
    label: str | None = None
    description: str | None = None
    standard_workflow_id: str | None = None
    seah_workflow_id: str | None = None
    actor_roles: list[TypeActorRoleItem] | None = None
    workflow_bindings: list[TypeWorkflowBindingItem] | None = None
    owner_organization_id: str | None = None
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
        actor_roles=row.actor_roles or [],
        workflow_bindings=row.workflow_bindings or [],
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


def _require_authority(db: Session, user: CurrentUser, owner_organization_id: str | None) -> None:
    """Who may author a type owned by ``owner_organization_id`` (§3.1).

    ``super_admin`` anywhere; an ``org_admin`` within its own subtree. A **global** type
    (owner NULL) is the platform's, so a scoped org_admin cannot edit it — it would be
    changing a template other organizations are offered.
    """
    if is_super_admin(user):
        return
    if not is_org_admin(user):
        raise HTTPException(
            status_code=403,
            detail="You cannot change project types. Ask your organization's administrator.",
        )
    reach = admin_org_scope_ids(db, user)
    if reach is None:  # country-wide org_admin — administers the whole tree
        return
    if owner_organization_id and owner_organization_id in reach:
        return
    raise HTTPException(
        status_code=403,
        detail=(
            "This project type belongs to another organization. Use it as a template to make "
            "your own copy."
            if owner_organization_id
            else "This project type is shared with every organization, so only the platform "
            "administrator can change it. Use it as a template to make your own copy."
        ),
    )


def _validate_config(
    db: Session,
    *,
    actor_roles: list[dict[str, Any]],
    workflow_bindings: list[dict[str, Any]],
) -> None:
    """Check the *resulting* configuration before it is stored.

    Raises 422 with a message an admin can act on (doc ui/05 §2.5 — no field names, no codes).
    """
    seen: set[str] = set()
    for entry in actor_roles:
        key = (entry.get("key") or "").strip()
        label = (entry.get("label") or "").strip()
        if not key or not label:
            raise HTTPException(status_code=422, detail="Every organization role needs a name.")
        if not ROLE_KEY_RE.match(key):
            raise HTTPException(
                status_code=422,
                detail=f"'{key}' is not a valid role key — use lowercase letters, digits and underscores.",
            )
        if key in seen:
            raise HTTPException(status_code=422, detail=f"'{label}' is listed twice.")
        seen.add(key)

    if workflow_bindings:
        from ticketing.services.project_workflows import validate_workflow_binding

        defaults = [b for b in workflow_bindings if b.get("is_default")]
        if len(defaults) != 1:
            raise HTTPException(
                status_code=422, detail="Mark exactly one workflow as the default."
            )
        claimed: dict[str, str] = {}
        for b in workflow_bindings:
            if not (b.get("display_label") or "").strip():
                raise HTTPException(status_code=422, detail="Give every workflow a name.")
            wf = validate_workflow_binding(db, str(b["workflow_id"]))
            sensitive = (wf.workflow_type or "").lower() == "seah"
            if b.get("is_default") and sensitive:
                raise HTTPException(
                    status_code=422,
                    detail="A sensitive workflow cannot be the default — the default takes every "
                    "grievance that matches nothing else.",
                )
            if not b.get("is_default") and not (b.get("intake_route") or "").strip():
                raise HTTPException(
                    status_code=422,
                    detail=f"Choose the chatbot menu that sends grievances to '{b['display_label']}'.",
                )
            for c in b.get("classifications") or []:
                if c in claimed and claimed[c] != b["display_label"]:
                    raise HTTPException(
                        status_code=422,
                        detail=f"Category '{c}' is already used by '{claimed[c]}'. A category "
                        "can be used by one workflow only.",
                    )
                claimed[c] = b["display_label"]


def _legacy_workflow_mirrors(
    db: Session, bindings: list[dict[str, Any]]
) -> tuple[str | None, str | None]:
    """`standard_workflow_id` / `seah_workflow_id` derived from the bindings.

    Both columns are legacy mirrors (doc 14 §4) — kept in sync here so the one authoring
    surface writes them and nothing has to remember to.
    """
    from ticketing.models.workflow import WorkflowDefinition

    standard = next((str(b["workflow_id"]) for b in bindings if b.get("is_default")), None)
    seah = None
    for b in bindings:
        wf = db.get(WorkflowDefinition, str(b["workflow_id"]))
        if wf and (wf.workflow_type or "").lower() == "seah":
            seah = str(b["workflow_id"])
            break
    return standard, seah


def _validate_owner(db: Session, owner_organization_id: str | None) -> None:
    if owner_organization_id and not db.get(Organization, owner_organization_id):
        raise HTTPException(
            status_code=422, detail=f"Organization '{owner_organization_id}' not found"
        )


@router.get("/project-types", response_model=list[ProjectTypeResponse])
def list_project_types(
    active_only: bool = True,
    owner_organization_id: str | None = None,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_admin),
):
    """List project types visible to the caller — global ones plus its own subtree's (§3.1).

    ``owner_organization_id`` is the **New project** filter: the types offered for that
    organization (its own, its parents', and the global ones).
    """
    rows = types_svc.list_project_types(
        db, active_only=active_only, user=_user, owner_organization_id=owner_organization_id
    )
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
    current_user: CurrentUser = Depends(require_admin),
):
    if types_svc.get_project_type(db, body.type_key):
        raise HTTPException(status_code=409, detail=f"Project type '{body.type_key}' already exists")
    # An org_admin's type is stamped with its own org node; super_admin may author a global
    # type (owner NULL) or place one under any organization.
    owner = body.owner_organization_id if is_super_admin(current_user) else catalog_owner_for(current_user)
    _require_authority(db, current_user, owner)
    _validate_owner(db, owner)
    actor_roles = [r.model_dump() for r in body.actor_roles]
    bindings = [b.model_dump() for b in body.workflow_bindings]
    _validate_config(db, actor_roles=actor_roles, workflow_bindings=bindings)
    standard_wf, seah_wf = (
        _legacy_workflow_mirrors(db, bindings)
        if bindings
        else (body.standard_workflow_id, body.seah_workflow_id)
    )
    now = _now()
    row = ProjectType(
        type_key=body.type_key,
        label=body.label,
        description=body.description,
        standard_workflow_id=standard_wf,
        seah_workflow_id=seah_wf,
        actor_roles=actor_roles,
        workflow_bindings=bindings,
        owner_organization_id=owner,
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
    current_user: CurrentUser = Depends(require_admin),
):
    row = types_svc.get_project_type(db, type_key)
    if not row:
        raise HTTPException(status_code=404, detail="Project type not found")
    fields = body.model_fields_set
    _require_authority(db, current_user, row.owner_organization_id)
    _require_editable(db, type_key, fields)
    if "owner_organization_id" in fields:
        # Moving a type to another organization is itself an authoring act in both places.
        _require_authority(db, current_user, body.owner_organization_id)
        _validate_owner(db, body.owner_organization_id)

    actor_roles = (
        [r.model_dump() for r in body.actor_roles] if body.actor_roles is not None else list(row.actor_roles or [])
    )
    bindings = (
        [b.model_dump() for b in body.workflow_bindings]
        if body.workflow_bindings is not None
        else list(row.workflow_bindings or [])
    )
    _validate_config(
        db,
        actor_roles=actor_roles,
        workflow_bindings=bindings if body.workflow_bindings is not None else [],
    )

    if body.label is not None:
        row.label = body.label
    if body.description is not None:
        row.description = body.description
    if body.actor_roles is not None:
        row.actor_roles = actor_roles
    if body.workflow_bindings is not None:
        row.workflow_bindings = bindings
        row.standard_workflow_id, row.seah_workflow_id = _legacy_workflow_mirrors(db, bindings)
    else:
        if body.standard_workflow_id is not None:
            row.standard_workflow_id = body.standard_workflow_id
        if body.seah_workflow_id is not None:
            row.seah_workflow_id = body.seah_workflow_id
    if "owner_organization_id" in fields:
        row.owner_organization_id = body.owner_organization_id
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
    current_user: CurrentUser = Depends(require_admin),
):
    src = types_svc.get_project_type(db, type_key)
    if not src:
        raise HTTPException(status_code=404, detail="Project type not found")
    if types_svc.get_project_type(db, body.type_key):
        raise HTTPException(status_code=409, detail=f"Project type '{body.type_key}' already exists")
    # The copy lands in the author's own organization — copying a type you may read but not
    # edit is exactly what "Use as template" is for, so authority is checked on the *copy*.
    owner = (
        (body.owner_organization_id or src.owner_organization_id)
        if is_super_admin(current_user)
        else (catalog_owner_for(current_user) or src.owner_organization_id)
    )
    _require_authority(db, current_user, owner)
    _validate_owner(db, owner)
    now = _now()
    row = ProjectType(
        type_key=body.type_key,
        label=body.label or f"{src.label} (copy)",
        description=src.description,
        standard_workflow_id=src.standard_workflow_id,
        seah_workflow_id=src.seah_workflow_id,
        # Carried, not authored — the column is retired and awaiting a cleanup migration.
        routing_org_role=src.routing_org_role,
        actor_roles=list(src.actor_roles or []),
        workflow_bindings=list(src.workflow_bindings or []),
        owner_organization_id=owner,
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
