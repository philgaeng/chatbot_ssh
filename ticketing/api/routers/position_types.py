# SPDX-License-Identifier: Apache-2.0

"""
Position types + the position→role matrix (OC-02, doc 16 §3.2 / §9).

    GET    /position-types                list (optional workflow_track / owner filter)
    POST   /position-types                create (admin)
    PATCH  /position-types/{id}           update (admin) — position_key is immutable
    DELETE /position-types/{id}           delete (admin) — guarded against in-use

Authoring is a standard-track structural action (doc 16 §7): super_admin or a
standard-track org_admin, gated on MANAGE_ORG_STRUCTURE — same gate as the org tree.
`default_role_key` / `reports_to_position_key` are string refs (no hard FK), validated
app-side against the role catalog / other position types, mirroring the SH-2 pattern.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ticketing.api.dependencies import CurrentUser, get_authenticated_user
from ticketing.models.base import get_db
from ticketing.models.organization import UNIT_TYPES, Organization
from ticketing.models.position_type import PositionType
from ticketing.models.user import Role
from ticketing.services.admin_access import (
    SettingsAction,
    apply_catalog_scope,
    catalog_owner_for,
    require_settings_write,
)
from ticketing.services.role_scope import role_scope_matches_track

router = APIRouter()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _slugify_key(raw: str) -> str:
    """lowercase ASCII slug, e.g. 'Senior Divisional Engineer' -> 'senior_divisional_engineer'."""
    return re.sub(r"[^a-z0-9]+", "_", (raw or "").strip().lower()).strip("_")


def _unique_position_key(db: Session, display_name: str) -> str:
    """Mint a unique, non-null slug from the title. Users never author position keys (the field
    isn't in PositionTypeCreate), so a numeric suffix (_2, _3…) disambiguates when two positions
    share a title — guaranteeing the key is always present and unique, and nothing that references
    it (reports_to_position_key, the reports-to picker) can break on a blank or duplicate value."""
    base = _slugify_key(display_name) or "position"
    key = base
    n = 2
    while (
        db.execute(select(PositionType).where(PositionType.position_key == key)).scalar_one_or_none()
        is not None
    ):
        key = f"{base}_{n}"
        n += 1
    return key


def _role_ok_for_position_track(role_scope: str | None, position_track: str) -> bool:
    """A position's default role must be usable on the position's track.

    A `both`-track position needs a role usable on *both* tracks (scope 'Both'/None);
    otherwise reuse the SH-2 single-track predicate.
    """
    if position_track == "both":
        return role_scope in ("Both", None)
    return role_scope_matches_track(role_scope, position_track)


class PositionTypeCreate(BaseModel):
    # A position is a display-only job title (DESIGN-cast-model §3.2). The modal is 4 fields,
    # one required (title). No position_key (server-minted from display_name). No role/tier
    # link (default_role_key), no workflow_track, no visibility_mode — those parallel
    # mechanisms retire; the tier is chosen at per-package staffing. owner_organization_id is
    # server-stamped from the author's scope (catalog_owner_for), never taken from the body.
    display_name: str
    display_name_ne: str | None = None
    allowed_unit_types: list[str] = []  # optional, now purely descriptive
    reports_to_position_key: str | None = None
    reports_to_locus: str | None = Field(None, pattern="^(same_unit|parent_unit)$")
    # No default_role_key / workflow_track / visibility_mode: a title carries no role/tier
    # (DESIGN-cast-model §3.2). The tier is chosen at per-package staffing.


class PositionTypeUpdate(BaseModel):
    # position_key intentionally omitted — immutable after create (mirrors roles.role_key).
    display_name: str | None = None
    display_name_ne: str | None = None
    allowed_unit_types: list[str] | None = None
    reports_to_position_key: str | None = None
    reports_to_locus: str | None = Field(None, pattern="^(same_unit|parent_unit)$")
    default_role_key: str | None = None
    visibility_mode: str | None = Field(None, pattern="^(none|direct_reports|subtree)$")
    workflow_track: str | None = Field(None, pattern="^(standard|seah|both)$")
    owner_organization_id: str | None = None


class PositionTypeResponse(BaseModel):
    position_type_id: str
    position_key: str
    display_name: str
    display_name_ne: str | None
    allowed_unit_types: list[str]
    reports_to_position_key: str | None
    reports_to_locus: str | None
    default_role_key: str | None
    visibility_mode: str
    workflow_track: str
    owner_organization_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


def _validate_matrix(
    db: Session,
    *,
    default_role_key: str | None,
    workflow_track: str,
    reports_to_position_key: str | None,
    allowed_unit_types: list[str] | None,
    owner_organization_id: str | None,
    self_position_key: str | None,
) -> None:
    """Validate the (now optional) matrix references against the current effective state.
    Raises 422. A null ``default_role_key`` is the new normal (a title carries no role) —
    only a *provided* role is checked for existence/track."""
    for ut in allowed_unit_types or []:
        if ut not in UNIT_TYPES:
            raise HTTPException(status_code=422, detail=f"Invalid unit_type '{ut}' in allowed_unit_types")

    if default_role_key:
        role = db.execute(
            select(Role).where(Role.role_key == default_role_key)
        ).scalar_one_or_none()
        if role is None:
            raise HTTPException(
                status_code=422,
                detail=f"default_role_key '{default_role_key}' does not exist in the role catalog",
            )
        if not _role_ok_for_position_track(role.workflow_scope, workflow_track):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"default_role_key '{default_role_key}' is a {role.workflow_scope or 'unscoped'} "
                    f"role, incompatible with a {workflow_track}-track position"
                ),
            )

    if reports_to_position_key:
        if self_position_key and reports_to_position_key == self_position_key:
            raise HTTPException(status_code=422, detail="A position type cannot report to itself")
        parent = db.execute(
            select(PositionType).where(PositionType.position_key == reports_to_position_key)
        ).scalar_one_or_none()
        if parent is None:
            raise HTTPException(
                status_code=422,
                detail=f"reports_to_position_key '{reports_to_position_key}' not found",
            )

    if owner_organization_id and not db.get(Organization, owner_organization_id):
        raise HTTPException(
            status_code=422, detail=f"owner_organization_id '{owner_organization_id}' not found"
        )


@router.get("/position-types", response_model=list[PositionTypeResponse])
def list_position_types(
    workflow_track: str | None = Query(None, description="Filter: this track + 'both'"),
    owner_organization_id: str | None = Query(None),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(get_authenticated_user),
):
    """List position types. (Org-scoped-catalog availability filtering is SH-7.)"""
    stmt = select(PositionType).order_by(PositionType.position_key)
    if workflow_track:
        stmt = stmt.where(PositionType.workflow_track.in_([workflow_track, "both"]))
    if owner_organization_id:
        stmt = stmt.where(PositionType.owner_organization_id == owner_organization_id)
    # SH-7 §S5: org-scoped catalog — a scoped org_admin sees global + own-subtree-owned only.
    stmt = apply_catalog_scope(stmt, db, _user, PositionType.owner_organization_id)
    return db.execute(stmt).scalars().all()


@router.post(
    "/position-types",
    response_model=PositionTypeResponse,
    status_code=201,
    summary="Create a position type (admin)",
)
def create_position_type(
    body: PositionTypeCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
):
    """Create a position type + matrix binding. Standard-track admin / super (doc 16 §7)."""
    require_settings_write(current_user, SettingsAction.MANAGE_ORG_STRUCTURE)
    if not body.display_name.strip():
        raise HTTPException(status_code=400, detail="display_name is required")
    # Server-minted from the title, always unique & non-null — never user-authored.
    key = _unique_position_key(db, body.display_name)

    # SH-7 §S5: org-scoped catalog — owner is server-stamped from the author's scope node
    # (NULL = global for super_admin / country-wide org_admin), never taken from the body.
    # Track is not a title attribute anymore, so the owner lookup is track-agnostic.
    owner_org = catalog_owner_for(current_user)

    # A title carries no role/track/visibility anymore (DESIGN-cast-model §3.2); those columns
    # keep their model defaults (default_role_key NULL). Only the still-present references
    # (unit types, reports-to, owner) are validated.
    _validate_matrix(
        db,
        default_role_key=None,
        workflow_track="standard",
        reports_to_position_key=body.reports_to_position_key,
        allowed_unit_types=body.allowed_unit_types,
        owner_organization_id=owner_org,
        self_position_key=key,
    )

    pt = PositionType(
        position_key=key,
        display_name=body.display_name.strip(),
        display_name_ne=body.display_name_ne,
        allowed_unit_types=body.allowed_unit_types or [],
        reports_to_position_key=body.reports_to_position_key,
        reports_to_locus=body.reports_to_locus,
        owner_organization_id=owner_org,
    )
    db.add(pt)
    db.commit()
    db.refresh(pt)
    return pt


@router.patch(
    "/position-types/{position_type_id}",
    response_model=PositionTypeResponse,
    summary="Update a position type (admin)",
)
def update_position_type(
    position_type_id: str,
    body: PositionTypeUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
):
    """Update a position type. position_key is immutable. Standard-track admin / super."""
    require_settings_write(current_user, SettingsAction.MANAGE_ORG_STRUCTURE)
    pt = db.get(PositionType, position_type_id)
    if not pt:
        raise HTTPException(status_code=404, detail="Position type not found")
    fields = body.model_fields_set

    # Validate the *resulting* effective state (body values union existing).
    _validate_matrix(
        db,
        default_role_key=body.default_role_key if "default_role_key" in fields and body.default_role_key else pt.default_role_key,
        workflow_track=body.workflow_track if "workflow_track" in fields and body.workflow_track else pt.workflow_track,
        reports_to_position_key=body.reports_to_position_key if "reports_to_position_key" in fields else pt.reports_to_position_key,
        allowed_unit_types=body.allowed_unit_types if "allowed_unit_types" in fields else pt.allowed_unit_types,
        owner_organization_id=body.owner_organization_id if "owner_organization_id" in fields else pt.owner_organization_id,
        self_position_key=pt.position_key,
    )

    if "display_name" in fields and body.display_name is not None:
        pt.display_name = body.display_name.strip()
    if "display_name_ne" in fields:
        pt.display_name_ne = body.display_name_ne
    if "allowed_unit_types" in fields and body.allowed_unit_types is not None:
        pt.allowed_unit_types = body.allowed_unit_types
    if "reports_to_position_key" in fields:
        pt.reports_to_position_key = body.reports_to_position_key
    if "reports_to_locus" in fields:
        pt.reports_to_locus = body.reports_to_locus
    if "default_role_key" in fields and body.default_role_key is not None:
        # Editing the matrix default does NOT re-sync existing holders (doc 16 §4); OC-03's
        # Manage UI offers a "review holders" prompt. No side effect here by design.
        pt.default_role_key = body.default_role_key
    if "visibility_mode" in fields and body.visibility_mode is not None:
        pt.visibility_mode = body.visibility_mode
    if "workflow_track" in fields and body.workflow_track is not None:
        pt.workflow_track = body.workflow_track
    if "owner_organization_id" in fields:
        pt.owner_organization_id = body.owner_organization_id

    pt.updated_at = _now()
    db.commit()
    db.refresh(pt)
    return pt


class PositionHolder(BaseModel):
    officer_position_id: str
    user_id: str
    organization_id: str
    reports_to_user_id: str | None = None
    is_active: bool


@router.get(
    "/position-types/{position_type_id}/holders",
    response_model=list[PositionHolder],
    summary="List officers holding a position type (RB frame 06 — review holders)",
)
def list_position_type_holders(
    position_type_id: str,
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> list[PositionHolder]:
    """The officers who hold this position type, for the Review-holders modal. Read-only;
    descriptive `officer_positions` rows (never an access-control source)."""
    if not db.get(PositionType, position_type_id):
        raise HTTPException(status_code=404, detail="Position type not found")
    from ticketing.models.officer_position import OfficerPosition

    stmt = (
        select(OfficerPosition)
        .where(OfficerPosition.position_type_id == position_type_id)
        .order_by(OfficerPosition.user_id)
    )
    if active_only:
        stmt = stmt.where(OfficerPosition.is_active.is_(True))
    rows = db.execute(stmt).scalars().all()
    return [
        PositionHolder(
            officer_position_id=r.officer_position_id,
            user_id=r.user_id,
            organization_id=r.organization_id,
            reports_to_user_id=r.reports_to_user_id,
            is_active=r.is_active,
        )
        for r in rows
    ]


@router.delete(
    "/position-types/{position_type_id}",
    status_code=204,
    summary="Delete a position type (admin)",
)
def delete_position_type(
    position_type_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> None:
    """Delete a position type, blocked (409) while in use. Standard-track admin / super."""
    require_settings_write(current_user, SettingsAction.MANAGE_ORG_STRUCTURE)
    pt = db.get(PositionType, position_type_id)
    if not pt:
        raise HTTPException(status_code=404, detail="Position type not found")

    reports_count = db.scalar(
        select(func.count())
        .select_from(PositionType)
        .where(PositionType.reports_to_position_key == pt.position_key)
    ) or 0
    # OC-03: block if any officer holds this position type (active or historical).
    from ticketing.models.officer_position import OfficerPosition

    holders_count = db.scalar(
        select(func.count())
        .select_from(OfficerPosition)
        .where(OfficerPosition.position_type_id == pt.position_type_id)
    ) or 0
    if reports_count or holders_count:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Position type is in use",
                "reports_count": reports_count,
                "holders_count": holders_count,
            },
        )

    db.delete(pt)
    db.commit()
