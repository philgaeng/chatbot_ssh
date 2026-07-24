"""
Officer positions — invite/staff an officer by position type (OC-03, doc 16 §3.3/§5.2).

    GET    /users/{user_id}/positions              list an officer's positions
    POST   /users/{user_id}/positions              assign a position (mints role + scope)
    DELETE /users/{user_id}/positions/{opid}       end a position (is_active=false)

Assigning a position **pre-fills** role (from the position→role matrix), org unit, and the
unit's office territory as the location scope; the admin's explicit fields always win. It
then routes through the SH-3-validated helpers (`validate_jurisdiction` → `create_scope_row`
+ `upsert_user_role_row`) to write the enforcement rows, and records the descriptive
`officer_positions` row. Positions are never read for access control.

Gated on INVITE_OFFICERS (doc 16 §7: project_admin / officer_admin / org_admin / super may
staff). Identity/Keycloak provisioning stays on `POST /users/invite`; this endpoint only
mints the role/scope/position rows for an officer.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ticketing.api.dependencies import CurrentUser, get_authenticated_user
from ticketing.models.base import get_db
from ticketing.models.officer_position import OfficerPosition
from ticketing.models.organization import Organization
from ticketing.models.position_type import PositionType
from ticketing.models.user import Role
from ticketing.services.admin_access import SettingsAction, require_settings_write

router = APIRouter()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PositionAssignRequest(BaseModel):
    position_type_id: str
    organization_id: str
    # Overrides — any of these, when set, beats the matrix / territory pre-fill.
    role_key: str | None = None
    location_code: str | None = None
    includes_children: bool | None = None
    project_id: str | None = None
    project_code: str | None = None
    package_id: str | None = None
    # HR/admin override only (deputation / acting); not used for supervision.
    reports_to_user_id: str | None = None


class OfficerPositionResponse(BaseModel):
    officer_position_id: str
    user_id: str
    position_type_id: str
    position_key: str | None = None
    position_display_name: str | None = None
    organization_id: str
    default_role_key: str | None = None
    reports_to_user_id: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


def _to_response(op: OfficerPosition, pt: PositionType | None) -> OfficerPositionResponse:
    return OfficerPositionResponse(
        officer_position_id=op.officer_position_id,
        user_id=op.user_id,
        position_type_id=op.position_type_id,
        position_key=pt.position_key if pt else None,
        position_display_name=pt.display_name if pt else None,
        organization_id=op.organization_id,
        default_role_key=pt.default_role_key if pt else None,
        reports_to_user_id=op.reports_to_user_id,
        is_active=op.is_active,
        created_at=op.created_at,
    )


@router.get("/users/{user_id}/positions", response_model=list[OfficerPositionResponse])
def list_officer_positions(
    user_id: str,
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(get_authenticated_user),
):
    """List an officer's positions (dual-hat → may be several)."""
    email = user_id.strip().lower()
    stmt = select(OfficerPosition).where(OfficerPosition.user_id == email)
    if active_only:
        stmt = stmt.where(OfficerPosition.is_active.is_(True))
    stmt = stmt.order_by(OfficerPosition.created_at)
    rows = db.execute(stmt).scalars().all()
    pts = {p.position_type_id: p for p in db.execute(select(PositionType)).scalars().all()}
    return [_to_response(op, pts.get(op.position_type_id)) for op in rows]


@router.post(
    "/users/{user_id}/positions",
    response_model=OfficerPositionResponse,
    status_code=201,
    summary="Assign a position to an officer (invite pre-fill)",
)
def assign_officer_position(
    user_id: str,
    body: PositionAssignRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
):
    """Staff an officer by position: pre-fill role/org/scope from the matrix + territory,
    admin overrides win, then mint the enforcement rows via the SH-3 helpers."""
    require_settings_write(current_user, SettingsAction.INVITE_OFFICERS)
    from ticketing.services.officer_admin import (
        JurisdictionInput,
        create_scope_row,
        upsert_user_role_row,
        validate_jurisdiction,
    )

    email = user_id.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=422, detail="Position assignment requires an email user id.")

    pt = db.get(PositionType, body.position_type_id)
    if pt is None:
        raise HTTPException(status_code=404, detail="Position type not found")
    org = db.get(Organization, body.organization_id)  # validate_jurisdiction re-checks (SH-3)

    # A title carries no role (DESIGN-cast-model §3.2): the role/tier binding is created by
    # per-package Cast staffing, not here. So the position row is purely descriptive and no
    # role is required. An explicit role_key (or a legacy position default) is still honoured for
    # back-compat — when present, we mint the enforcement rows as before; when absent, we only
    # record the descriptive position and access comes from Cast staffing.
    role_key = body.role_key or pt.default_role_key
    if role_key:
        location_code = (
            body.location_code if body.location_code is not None
            else (org.territory_location_code if org else None)
        )
        includes_children = (
            body.includes_children if body.includes_children is not None
            else (org.territory_includes_children if org else False)
        )

        juris = JurisdictionInput(
            organization_id=body.organization_id,
            role_key=role_key,
            location_code=location_code,
            project_id=body.project_id,
            project_code=body.project_code,
            package_id=body.package_id,
            includes_children=includes_children,
        )
        resolved_pc = validate_jurisdiction(db, juris, require_jurisdiction=True)

        role = db.execute(select(Role).where(Role.role_key == role_key)).scalar_one_or_none()
        if role is None:
            raise HTTPException(status_code=404, detail=f"Role not found: {role_key}")

        # Enforcement rows via the only sanctioned writers (no direct inserts).
        upsert_user_role_row(db, email, role, body.organization_id, location_code)
        create_scope_row(db, email, juris, resolved_pc)

    op = OfficerPosition(
        user_id=email,
        position_type_id=pt.position_type_id,
        organization_id=body.organization_id,
        reports_to_user_id=body.reports_to_user_id,
        is_active=True,
    )
    db.add(op)
    db.commit()
    db.refresh(op)
    return _to_response(op, pt)


@router.delete(
    "/users/{user_id}/positions/{officer_position_id}",
    status_code=204,
    summary="End an officer position (transfer/deactivate)",
)
def end_officer_position(
    user_id: str,
    officer_position_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> None:
    """End a position (``is_active=false``). Does NOT remove the officer's role/scope rows —
    a transfer ends the old position without silently re-scoping (doc 16 §4 / DECISION)."""
    require_settings_write(current_user, SettingsAction.INVITE_OFFICERS)
    email = user_id.strip().lower()
    op = db.get(OfficerPosition, officer_position_id)
    if op is None or op.user_id != email:
        raise HTTPException(status_code=404, detail="Officer position not found")
    op.is_active = False
    op.updated_at = _now()
    db.commit()
