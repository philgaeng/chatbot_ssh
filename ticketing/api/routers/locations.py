"""
Locations, Countries, Organizations, and Projects — read + admin CRUD endpoints.

Endpoints:
    GET    /organizations                      list organizations
    POST   /organizations                      create organization (admin)
    PATCH  /organizations/{id}                 update organization (admin)
    GET  /countries                           list countries
    GET  /locations?country=NP&level=2&parent=P1&q=bira   browse tree
    GET  /locations/{location_code}           single node + translations

    GET  /locations/import/template.csv       download blank CSV template (super_admin)
    GET  /locations/import/template.json      download blank JSON template (super_admin)
    POST /locations/import                    upload CSV or JSON file (super_admin)

    GET  /projects                            list projects (filterable)
    POST /projects                            create project (admin)
    GET  /projects/{project_id}               project detail
    PATCH /projects/{project_id}              update project (admin)

    GET  /projects/{project_id}/organizations
    POST /projects/{project_id}/organizations/{organization_id}
    DELETE /projects/{project_id}/organizations/{organization_id}

    GET  /projects/{project_id}/locations
    POST /projects/{project_id}/locations/{location_code}
    DELETE /projects/{project_id}/locations/{location_code}
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session, selectinload

from ticketing.api.dependencies import CurrentUser, get_authenticated_user, require_admin, require_super_admin
from ticketing.constants.entity_codes import EntityCodeError, validate_entity_code
from ticketing.services import entity_codes as entity_codes_svc
from ticketing.services.admin_access import (
    SettingsAction,
    can_admin_org,
    can_assign_project_workflow,
    is_super_admin,
    require_settings_write,
    require_track_for_mutation,
)
from ticketing.services import project_workflows as pw_svc
from ticketing.models.base import get_db
from ticketing.models.country import Country, Location, LocationLevelDef, LocationTranslation
from ticketing.models.organization import Organization
from ticketing.services.org_tree import (
    INSTITUTIONAL_CATEGORIES,
    ORG_CATEGORIES,
    UNIT_TYPES,
    descendant_org_ids,
    would_create_cycle,
)
from ticketing.services.org_dedup import (
    OrgRecord,
    find_duplicate_candidates,
)
from ticketing.utils.organization_identifier import (
    allocate_unique_organization_id,
    ascii_alnum,
    suggested_organization_id,
)
from ticketing.models.officer_scope import OfficerScope
from ticketing.models.package import PackageLocation, PackageOrganization, ProjectPackage
from ticketing.models.project import (
    Project,
    ProjectActorRole,
    ProjectDonor,
    ProjectLocation,
    ProjectOrganization,
)
from ticketing.services import project_actor_roles as actor_roles_svc
from ticketing.api.schemas.project_messaging import (
    ProjectMessagingPatch,
    ProjectMessagingResponse,
)
from ticketing.services import officer_messaging as msg_svc
from ticketing.services import donor_guardrail as donor_guardrail_svc
from ticketing.services import project_go_live as go_live_svc
from ticketing.services import project_types as types_svc
from ticketing.models.ticket import Ticket
from ticketing.models.user import UserRole
from ticketing.models.workflow import WorkflowAssignment

router = APIRouter()

UTC = timezone.utc


def _now() -> datetime:
    return datetime.now(UTC)


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class CountryResponse(BaseModel):
    country_code: str
    name: str
    level_defs: list[dict[str, Any]] = []

    model_config = {"from_attributes": True}


class LocationTranslationResponse(BaseModel):
    lang_code: str
    name: str

    model_config = {"from_attributes": True}


class LocationResponse(BaseModel):
    location_code: str
    country_code: str
    level_number: int
    parent_location_code: str | None
    source_id: int | None
    is_active: bool
    translations: list[LocationTranslationResponse] = []

    model_config = {"from_attributes": True}


class ProjectCreate(BaseModel):
    country_code: str = Field(..., max_length=8)
    short_code: str = Field(..., max_length=8)
    name: str
    description: str | None = None
    is_active: bool | None = None
    project_type_key: str | None = Field(
        None,
        description="Archetype to instantiate (e.g. construction_road). Defaults workflows and actor roles.",
    )
    # doc 13 / DECISION 2026-07-10 §2: the accountable government agency (routing anchor).
    implementing_agency_org_id: str | None = Field(None, max_length=64)

    @field_validator("short_code", mode="before")
    @classmethod
    def _normalize_short_code(cls, v: object) -> str:
        try:
            return validate_entity_code(str(v) if v is not None else "", field="Project code")
        except EntityCodeError as exc:
            raise ValueError(str(exc)) from exc


class ProjectUpdate(BaseModel):
    name: str | None = None
    short_code: str | None = Field(None, max_length=8)
    description: str | None = None
    is_active: bool | None = None
    standard_workflow_id: str | None = None
    seah_workflow_id: str | None = None
    # doc 13 / DECISION 2026-07-10 §2: the accountable government agency (routing anchor).
    implementing_agency_org_id: str | None = Field(None, max_length=64)

    @field_validator("short_code", mode="before")
    @classmethod
    def _normalize_short_code(cls, v: object) -> str | None:
        if v is None or (isinstance(v, str) and not str(v).strip()):
            return None
        try:
            return validate_entity_code(str(v), field="Project code")
        except EntityCodeError as exc:
            raise ValueError(str(exc)) from exc


class ProjectOrgItem(BaseModel):
    """Organization linked to a project, with its role in that project."""
    organization_id: str
    org_role: str | None = None

    model_config = {"from_attributes": True}


class ProjectWorkflowItem(BaseModel):
    project_workflow_id: str
    workflow_id: str
    display_label: str
    classifications: list[str] = []
    intake_route: str | None = None
    is_default: bool = False
    workflow_track: str = "standard"
    sort_order: int = 0


class ProjectWorkflowUpsert(BaseModel):
    display_label: str = Field(..., max_length=200)
    workflow_id: str = Field(..., max_length=36)
    classifications: list[str] = []
    intake_route: str | None = None
    is_default: bool = False
    sort_order: int | None = None


class ProjectWorkflowsReplace(BaseModel):
    items: list[ProjectWorkflowUpsert]


class ProjectResponse(BaseModel):
    project_id: str
    country_code: str
    short_code: str
    name: str
    description: str | None
    is_active: bool
    project_type_key: str | None = None
    standard_workflow_id: str | None = None
    seah_workflow_id: str | None = None
    implementing_agency_org_id: str | None = None
    donor_org_ids: list[str] = []
    workflow_slots: list[ProjectWorkflowItem] = []
    officer_messaging: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
    organizations: list[ProjectOrgItem] = []
    location_codes: list[str] = []

    model_config = {"from_attributes": True}


class GoLiveCheckResponse(BaseModel):
    id: str
    label: str
    group: str
    severity: str
    status: str
    message: str
    section: str | None = None


class GoLiveReportResponse(BaseModel):
    checks: list[GoLiveCheckResponse]
    can_activate: bool
    can_accept_tickets: bool
    summary: dict[str, int]


# ── Organizations ─────────────────────────────────────────────────────────────

class OrganizationResponse(BaseModel):
    organization_id: str
    name: str
    country_code: str | None
    is_active: bool
    default_language: str = "ne"
    # Org tree (OC-01, doc 16 §3.1)
    parent_organization_id: str | None = None
    org_category: str
    unit_type: str | None = None
    territory_location_code: str | None = None
    territory_includes_children: bool = False
    display_name_ne: str | None = None
    # Duplicate-candidate signals (SH-4). Non-PII org contact fields.
    email: str | None = None
    address: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrganizationCreate(BaseModel):
    organization_id: str | None = Field(
        default=None,
        max_length=64,
        description="Optional short uppercase key. Omit to auto-generate from name + country.",
    )
    name: str
    country_code: str | None = None
    is_active: bool = True
    default_language: str = "ne"
    # Org tree (OC-01). parent NULL = root. org_category is required-ish for roots
    # (defaults to 'government' if omitted) and always inherited from parent for children.
    parent_organization_id: str | None = None
    org_category: str | None = None
    unit_type: str | None = None
    territory_location_code: str | None = None
    territory_includes_children: bool = False
    display_name_ne: str | None = None
    # Duplicate-candidate signals (SH-4). Populated so the fuzzy finder can match on them.
    email: str | None = Field(default=None, max_length=255)
    address: str | None = None


class OrganizationUpdate(BaseModel):
    name: str | None = None
    country_code: str | None = None
    is_active: bool | None = None
    default_language: str | None = None
    # Org tree (OC-01). Field-presence (model_fields_set) distinguishes "unset" from an
    # explicit null (e.g. detach-to-root), so these are only applied when supplied.
    parent_organization_id: str | None = None
    org_category: str | None = None
    unit_type: str | None = None
    territory_location_code: str | None = None
    territory_includes_children: bool | None = None
    display_name_ne: str | None = None
    # Duplicate-candidate signals (SH-4). model_fields_set distinguishes unset from an
    # explicit null (clear the field), so these apply only when supplied.
    email: str | None = Field(default=None, max_length=255)
    address: str | None = None


def _order_for_tree(orgs: list[Organization]) -> list[Organization]:
    """Depth-first order (each parent immediately before its children) for tree rendering.

    A node whose parent is outside the returned set (a true root, or the root of a
    ``root_id`` subtree) is treated as a top-level node.
    """
    by_id = {o.organization_id: o for o in orgs}
    children: dict[str, list[Organization]] = {}
    roots: list[Organization] = []
    for o in orgs:
        p = o.parent_organization_id
        if p and p in by_id:
            children.setdefault(p, []).append(o)
        else:
            roots.append(o)

    ordered: list[Organization] = []

    def _walk(node: Organization) -> None:
        ordered.append(node)
        for child in sorted(children.get(node.organization_id, []), key=lambda x: x.organization_id):
            _walk(child)

    for root in sorted(roots, key=lambda x: x.organization_id):
        _walk(root)
    return ordered


@router.get("/organizations", response_model=list[OrganizationResponse])
def list_organizations(
    country: str | None = Query(None),
    active_only: bool = Query(True),
    root_id: str | None = Query(
        None, description="Restrict to this organization and its descendants (subtree)."
    ),
    tree: bool = Query(
        False, description="Order parents-before-children (depth-first) for tree rendering."
    ),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(get_authenticated_user),  # SH-4 (OC-06 F16): was fully open
):
    """List organizations. ``root_id`` filters to a subtree; ``tree`` orders for rendering."""
    stmt = select(Organization)
    if country:
        stmt = stmt.where(Organization.country_code == country)
    if active_only:
        stmt = stmt.where(Organization.is_active.is_(True))
    if root_id:
        subtree = descendant_org_ids(db, root_id, include_self=True)
        if not subtree:
            return []
        stmt = stmt.where(Organization.organization_id.in_(subtree))
    stmt = stmt.order_by(Organization.organization_id)
    orgs = list(db.execute(stmt).scalars().all())
    if tree:
        orgs = _order_for_tree(orgs)
    return orgs


@router.post("/organizations", response_model=OrganizationResponse, status_code=201,
             summary="Create an organization (admin)")
def create_organization(
    body: OrganizationCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
):
    """Create a new organization. Standard-track country admin or super_admin (doc 16 §7)."""
    require_settings_write(current_user, SettingsAction.MANAGE_ORG_STRUCTURE)
    name_clean = body.name.strip()
    if not name_clean:
        raise HTTPException(status_code=400, detail="Name is required")
    if body.country_code and not db.get(Country, body.country_code):  # SH-4 (OC-06 F18)
        raise HTTPException(status_code=422, detail=f"Country '{body.country_code}' not found")

    # ── Org tree (OC-01, doc 16 §3.1) ─────────────────────────────────────────
    if body.unit_type and body.unit_type not in UNIT_TYPES:
        raise HTTPException(status_code=422, detail=f"Invalid unit_type '{body.unit_type}'")

    parent: Organization | None = None
    if body.parent_organization_id:
        parent = db.get(Organization, body.parent_organization_id)
        if parent is None:
            raise HTTPException(
                status_code=422,
                detail=f"Parent organization '{body.parent_organization_id}' not found",
            )

    if parent is not None:
        # Children inherit the root's category (authoritative). An explicit, mismatched
        # category is a mistake — reject it rather than silently ignore.
        org_category = parent.org_category
        if body.org_category and body.org_category != org_category:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"org_category '{body.org_category}' conflicts with inherited "
                    f"'{org_category}' — children inherit the root's category"
                ),
            )
    else:
        # Root. org_category defaults to 'government' when omitted (matches the model /
        # migration backfill).
        org_category = body.org_category or "government"
        if org_category not in ORG_CATEGORIES:
            raise HTTPException(status_code=422, detail=f"Invalid org_category '{org_category}'")

    # SH-7 §S3: org_category root-creation gating + sub-unit subtree enforcement (doc 11 §2).
    if not is_super_admin(current_user):
        if parent is None:
            if org_category in INSTITUTIONAL_CATEGORIES:
                raise HTTPException(
                    status_code=403,
                    detail=(
                        "Only super_admin can create a new government / local_government / "
                        "donor root organization"
                    ),
                )
            # A third_party root (contractor) is delegable to a standard org_admin, which
            # the MANAGE_ORG_STRUCTURE gate above already confirmed.
        elif not can_admin_org(db, current_user, parent.organization_id, "standard"):
            raise HTTPException(
                status_code=403,
                detail="Your org_admin scope does not cover this parent organization",
            )

    if body.territory_location_code and not db.get(Location, body.territory_location_code):
        raise HTTPException(
            status_code=422,
            detail=f"territory_location_code '{body.territory_location_code}' not found",
        )

    raw = body.organization_id.strip() if body.organization_id else ""
    if raw:
        org_id = ascii_alnum(raw.upper(), keep_underscore=True)  # SH-6: ASCII-only ids
        if not org_id:
            raise HTTPException(status_code=400, detail="Invalid organization_id")
        if db.get(Organization, org_id):
            raise HTTPException(status_code=409, detail=f"Organization '{org_id}' already exists")
    else:
        base = suggested_organization_id(name_clean, body.country_code)
        if not base:
            raise HTTPException(
                status_code=400,
                detail="Could not derive organization_id from name; provide organization_id explicitly.",
            )
        org_id = allocate_unique_organization_id(db, base)
    org = Organization(
        organization_id=org_id,
        name=name_clean,
        country_code=body.country_code or None,
        is_active=body.is_active,
        default_language=body.default_language,
        parent_organization_id=parent.organization_id if parent else None,
        org_category=org_category,
        unit_type=body.unit_type,
        territory_location_code=body.territory_location_code,
        territory_includes_children=body.territory_includes_children,
        display_name_ne=body.display_name_ne,
        email=(body.email or "").strip() or None,
        address=(body.address or "").strip() or None,
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


# ── Duplicate-candidate finder (SH-4, design §2.4) ───────────────────────────────

class DuplicateCheckRequest(BaseModel):
    """Proposed org to fuzzy-match against the registry (a preview — no write)."""
    name: str
    email: str | None = None
    address: str | None = None
    country_code: str | None = None
    # On update, exclude the org being edited so it never matches itself.
    exclude_organization_id: str | None = None
    limit: int = Field(8, ge=1, le=50)


class DuplicateCandidateItem(BaseModel):
    organization_id: str
    name: str
    score: float
    reasons: list[str]
    name_score: float
    email_domain_match: bool
    address_score: float
    # Display context for the soft-flag row ("Possible duplicate: … (contractor, Jhapa)").
    country_code: str | None = None
    org_category: str | None = None
    unit_type: str | None = None


@router.post(
    "/organizations/duplicate-candidates",
    response_model=list[DuplicateCandidateItem],
    summary="Fuzzy duplicate-candidate finder for an org (soft flag — never blocks create)",
)
def find_organization_duplicate_candidates(
    body: DuplicateCheckRequest,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(get_authenticated_user),
):
    """Return likely-duplicate organizations for a proposed ``{name, email, address}``.

    This is a **soft-flag preview** (SH-4, design §2.4): the UI shows "Possible duplicate:
    {org} · Use existing / Create anyway". It **never** blocks creation — creation stays on
    ``POST /organizations`` and is unaffected by this result. Matching (pure logic in
    ``ticketing/services/org_dedup.py``) uses distinctive name tokens (generic-word
    stoplist), corporate email domain (free providers ignored), and fuzzy address.

    Read/preview only, so it requires just an authenticated user — not the
    ``MANAGE_ORG_STRUCTURE`` write gate that ``POST/PATCH/DELETE /organizations`` carry.
    """
    name = (body.name or "").strip()
    if not name:
        return []

    # DB-level pre-filter to bound the scan (the matcher itself is country-agnostic):
    # compare within the same country plus country-less orgs (e.g. ADB). With no country
    # supplied, scan everything.
    stmt = select(Organization)
    if body.country_code:
        stmt = stmt.where(
            or_(
                Organization.country_code == body.country_code,
                Organization.country_code.is_(None),
            )
        )
    orgs = list(db.execute(stmt).scalars().all())
    by_id = {o.organization_id: o for o in orgs}

    proposed = OrgRecord(
        name=name,
        email=body.email,
        address=body.address,
        country_code=body.country_code,
    )
    existing = [
        OrgRecord(
            name=o.name,
            organization_id=o.organization_id,
            email=o.email,
            address=o.address,
            country_code=o.country_code,
        )
        for o in orgs
    ]
    candidates = find_duplicate_candidates(
        proposed,
        existing,
        exclude_id=body.exclude_organization_id,
        limit=body.limit,
    )
    out: list[DuplicateCandidateItem] = []
    for c in candidates:
        org = by_id.get(c.organization_id)
        out.append(
            DuplicateCandidateItem(
                organization_id=c.organization_id,
                name=c.name,
                score=c.score,
                reasons=c.reasons,
                name_score=c.name_score,
                email_domain_match=c.email_domain_match,
                address_score=c.address_score,
                country_code=org.country_code if org else None,
                org_category=org.org_category if org else None,
                unit_type=org.unit_type if org else None,
            )
        )
    return out


@router.patch("/organizations/{organization_id}", response_model=OrganizationResponse,
              summary="Update an organization (admin)")
def update_organization(
    organization_id: str,
    body: OrganizationUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
):
    """Update organization fields incl. tree placement. Standard-track admin / super (doc 16 §7)."""
    require_settings_write(current_user, SettingsAction.MANAGE_ORG_STRUCTURE)
    org = db.get(Organization, organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    # SH-7 §S3: an org_admin may only edit within its own subtree.
    if not is_super_admin(current_user) and not can_admin_org(
        db, current_user, organization_id, "standard"
    ):
        raise HTTPException(
            status_code=403, detail="Your org_admin scope does not cover this organization"
        )
    fields = body.model_fields_set
    if body.name is not None:
        org.name = body.name.strip()
    if body.country_code is not None:
        if body.country_code and not db.get(Country, body.country_code):  # SH-4 (OC-06 F18)
            raise HTTPException(status_code=422, detail=f"Country '{body.country_code}' not found")
        org.country_code = body.country_code or None
    if body.is_active is not None:
        org.is_active = body.is_active
    if body.default_language is not None:
        org.default_language = body.default_language

    # ── Org tree (OC-01, doc 16 §3.1) ─────────────────────────────────────────
    if "unit_type" in fields:
        if body.unit_type and body.unit_type not in UNIT_TYPES:
            raise HTTPException(status_code=422, detail=f"Invalid unit_type '{body.unit_type}'")
        org.unit_type = body.unit_type
    if "territory_location_code" in fields:
        if body.territory_location_code and not db.get(Location, body.territory_location_code):
            raise HTTPException(
                status_code=422,
                detail=f"territory_location_code '{body.territory_location_code}' not found",
            )
        org.territory_location_code = body.territory_location_code
    if "territory_includes_children" in fields and body.territory_includes_children is not None:
        org.territory_includes_children = body.territory_includes_children
    if "display_name_ne" in fields:
        org.display_name_ne = body.display_name_ne
    # Duplicate-candidate signals (SH-4) — apply only when supplied; "" clears to NULL.
    if "email" in fields:
        org.email = (body.email or "").strip() or None
    if "address" in fields:
        org.address = (body.address or "").strip() or None

    # Category is inherited from the root, so it moves with the parent. Compute the new
    # category (if any) and cascade it to the whole subtree.
    new_category: str | None = None
    cascade = False
    if "parent_organization_id" in fields:
        new_parent_id = body.parent_organization_id or None
        if new_parent_id:
            parent = db.get(Organization, new_parent_id)
            if parent is None:
                raise HTTPException(
                    status_code=422, detail=f"Parent organization '{new_parent_id}' not found"
                )
            if would_create_cycle(db, organization_id, new_parent_id):
                raise HTTPException(
                    status_code=422,
                    detail="Reparenting would create a cycle (a node cannot report to its own descendant)",
                )
            # SH-7 §S3: the destination parent must also be within the admin's subtree.
            if not is_super_admin(current_user) and not can_admin_org(
                db, current_user, new_parent_id, "standard"
            ):
                raise HTTPException(
                    status_code=403,
                    detail="Your org_admin scope does not cover the destination parent",
                )
            org.parent_organization_id = new_parent_id
            new_category = parent.org_category
        else:
            # Detach to root — keep the current category unless a new one is supplied.
            org.parent_organization_id = None
            new_category = body.org_category or org.org_category
            if new_category not in ORG_CATEGORIES:
                raise HTTPException(status_code=422, detail=f"Invalid org_category '{new_category}'")
        org.org_category = new_category
        cascade = True
    elif "org_category" in fields and body.org_category is not None:
        # Directly settable only on a root; children inherit.
        if org.parent_organization_id is not None:
            raise HTTPException(
                status_code=422,
                detail="A child organization inherits its category from the root; set it on the root.",
            )
        if body.org_category not in ORG_CATEGORIES:
            raise HTTPException(status_code=422, detail=f"Invalid org_category '{body.org_category}'")
        if body.org_category != org.org_category:
            org.org_category = body.org_category
            new_category = body.org_category
            cascade = True

    if cascade and new_category is not None:
        db.flush()  # make org's own change visible before walking its subtree
        descendants = descendant_org_ids(db, organization_id, include_self=False)
        if descendants:
            db.execute(
                update(Organization)
                .where(Organization.organization_id.in_(descendants))
                .values(org_category=new_category, updated_at=_now())
            )

    org.updated_at = _now()
    db.commit()
    db.refresh(org)
    return org


@router.delete(
    "/organizations/{organization_id}",
    status_code=204,
    summary="Delete organization (admin)",
)
def delete_organization(
    organization_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> None:
    """Delete an organization. Standard-track org_admin (own subtree) or super_admin (doc 16 §7)."""
    require_settings_write(current_user, SettingsAction.MANAGE_ORG_STRUCTURE)
    org = db.get(Organization, organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    # SH-7 §S3: an org_admin may only delete within its own subtree.
    if not is_super_admin(current_user) and not can_admin_org(
        db, current_user, organization_id, "standard"
    ):
        raise HTTPException(
            status_code=403, detail="Your org_admin scope does not cover this organization"
        )

    # OC-01: block deleting a parent — the self-FK is ON DELETE SET NULL, which would
    # silently orphan the subtree (turn children into roots). Reparent/remove them first.
    child_count = db.scalar(
        select(func.count())
        .select_from(Organization)
        .where(Organization.parent_organization_id == organization_id)
    ) or 0
    if child_count:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete: {child_count} child organization(s) report to this org. "
            f"Reassign or delete them first.",
        )

    ticket_count = db.scalar(
        select(func.count()).select_from(Ticket).where(Ticket.organization_id == organization_id)
    ) or 0
    if ticket_count:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete: {ticket_count} ticket(s) reference this organization.",
        )

    role_count = db.scalar(
        select(func.count()).select_from(UserRole).where(UserRole.organization_id == organization_id)
    ) or 0
    if role_count:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete: {role_count} officer role assignment(s) use this organization.",
        )

    scope_count = db.scalar(
        select(func.count())
        .select_from(OfficerScope)
        .where(OfficerScope.organization_id == organization_id)
    ) or 0
    if scope_count:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete: {scope_count} officer scope(s) use this organization.",
        )

    assign_count = db.scalar(
        select(func.count())
        .select_from(WorkflowAssignment)
        .where(WorkflowAssignment.organization_id == organization_id)
    ) or 0
    if assign_count:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete: {assign_count} workflow assignment(s) use this organization.",
        )

    pkg_count = db.scalar(
        select(func.count())
        .select_from(PackageOrganization)
        .where(PackageOrganization.organization_id == organization_id)
    ) or 0
    if pkg_count:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete: {pkg_count} package actor assignment(s) use this organization.",
        )

    # SH-4 (OC-06 F7): project actor links were NOT guarded (unlike package links), so a
    # delete cascade-orphaned the ProjectOrganization row silently. Guard it symmetrically.
    proj_count = db.scalar(
        select(func.count())
        .select_from(ProjectOrganization)
        .where(ProjectOrganization.organization_id == organization_id)
    ) or 0
    if proj_count:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete: {proj_count} project actor assignment(s) use this organization.",
        )

    db.delete(org)
    db.commit()


# ── Organization tree CSV import (OC-01, doc 16 §9) ──────────────────────────────

class OrgImportResult(BaseModel):
    organizations_upserted: int
    dry_run: bool
    errors: list[str] = []


@router.get(
    "/organizations/import/template.csv",
    response_class=PlainTextResponse,
    summary="Download blank CSV template for org tree import (admin)",
)
def download_org_csv_template(
    current_user: CurrentUser = Depends(get_authenticated_user),
):
    """Blank org-tree CSV template. Columns: organization_id, name, parent_organization_id,
    org_category, unit_type, country_code, territory_location_code,
    territory_includes_children, display_name_ne."""
    require_settings_write(current_user, SettingsAction.MANAGE_ORG_STRUCTURE)
    from ticketing.seed.org_import_core import CSV_TEMPLATE
    return PlainTextResponse(
        content=CSV_TEMPLATE,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="organization_template.csv"'},
    )


@router.post(
    "/organizations/import",
    response_model=OrgImportResult,
    status_code=200,
    summary="Import an org tree from CSV (admin) — whole-file validate, single transaction",
)
async def import_organizations(
    file: UploadFile = File(..., description="CSV org-tree file"),
    dry_run: bool = Form(False, description="Validate + parse only — do not write to DB"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
):
    """Upsert an org tree from CSV. Standard-track admin or super_admin (doc 16 §7).

    All-or-nothing: the entire file is validated first (required fields, domains, parent
    resolution, cycles, category inheritance). On any error nothing is written and the
    errors are returned; otherwise rows are upserted parents-first in a single transaction
    (idempotent — re-importing updates existing rows by ``organization_id``).
    """
    require_settings_write(current_user, SettingsAction.MANAGE_ORG_STRUCTURE)
    from ticketing.seed.org_import_core import parse_org_csv, plan_import, upsert_organizations

    raw = await file.read()
    try:
        rows = parse_org_csv(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"File parse error: {exc}")
    if not rows:
        raise HTTPException(status_code=422, detail="No organization rows found in file")

    # DB-shaped checks: external parents' categories (for inheritance), countries, territories.
    in_file_ids = {r.organization_id for r in rows if r.organization_id}
    external_cats: dict[str, str] = {}
    for pid in sorted(
        {r.parent_organization_id for r in rows if r.parent_organization_id and r.parent_organization_id not in in_file_ids}
    ):
        parent = db.get(Organization, pid)
        if parent is not None:
            external_cats[pid] = parent.org_category
        # A missing external parent is reported by plan_import ("not found").

    db_errors: list[str] = []
    for cc in sorted({r.country_code for r in rows if r.country_code}):
        if not db.get(Country, cc):
            db_errors.append(f"country_code '{cc}' not found")
    for lc in sorted({r.territory_location_code for r in rows if r.territory_location_code}):
        if not db.get(Location, lc):
            db_errors.append(f"territory_location_code '{lc}' not found")

    plan = plan_import(rows, external_org_categories=external_cats)
    all_errors = plan.errors + db_errors
    if all_errors:
        raise HTTPException(
            status_code=422,
            detail={"message": "Import rejected — nothing written", "errors": all_errors},
        )

    if dry_run:
        return OrgImportResult(organizations_upserted=len(plan.ordered_rows), dry_run=True)

    try:
        count = upsert_organizations(plan.ordered_rows, plan.resolved_categories, db)
        db.commit()
    except Exception as exc:  # pragma: no cover - defensive
        db.rollback()
        raise HTTPException(status_code=500, detail=f"DB write failed: {exc}") from exc

    return OrgImportResult(organizations_upserted=count, dry_run=False)


# ── Countries ─────────────────────────────────────────────────────────────────

@router.get("/countries", response_model=list[CountryResponse])
def list_countries(db: Session = Depends(get_db)):
    """List all countries with their admin-level definitions."""
    rows = db.execute(
        select(Country).options(selectinload(Country.level_defs)).order_by(Country.country_code)
    ).scalars().all()
    result = []
    for c in rows:
        result.append({
            "country_code": c.country_code,
            "name": c.name,
            "level_defs": [
                {
                    "level_number": ld.level_number,
                    "level_name_en": ld.level_name_en,
                    "level_name_local": ld.level_name_local,
                }
                for ld in sorted(c.level_defs, key=lambda x: x.level_number)
            ],
        })
    return result


# ── Location import (super_admin only) ───────────────────────────────────────

@router.get(
    "/locations/import/template.csv",
    response_class=PlainTextResponse,
    summary="Download blank CSV template for location import (super_admin)",
    tags=["Locations & Projects"],
)
def download_csv_template():
    """
    Returns a pre-formatted CSV template.
    Fill in the rows and upload via POST /locations/import.

    Columns:
      - location_code        unique code, e.g. P1 / P1_JHA / P1_JHA_BIR (see LOCATION_CODES.md)
      - level_number         1=Province, 2=District, 3=Municipality
      - parent_location_code code of the parent node (blank for level-1 nodes)
      - source_id            optional original numeric ID from your dataset
      - name_en              English name
      - name_XX              additional language columns (e.g. name_ne for Nepali)
    """
    from ticketing.seed.location_import_core import CSV_TEMPLATE
    return PlainTextResponse(
        content=CSV_TEMPLATE,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="location_template.csv"'},
    )


@router.get(
    "/locations/import/template.json",
    summary="Download blank JSON template for location import (super_admin)",
    tags=["Locations & Projects"],
)
def download_json_template():
    """
    Returns a nested province/district/municipality JSON template.
    Matches the structure of en_cleaned.json.
    Fill in the data and upload the English file (plus optional language files)
    via POST /locations/import?format=json.
    """
    from ticketing.seed.location_import_core import JSON_TEMPLATE
    return Response(
        content=json.dumps(JSON_TEMPLATE, indent=2, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="location_template.json"'},
    )


class ImportResult(BaseModel):
    country: str
    format: str
    locations_upserted: int
    translations_upserted: int
    dry_run: bool


@router.post(
    "/locations/import",
    response_model=ImportResult,
    status_code=200,
    summary="Upload a CSV or JSON file to import locations (super_admin only)",
    tags=["Locations & Projects"],
)
async def import_locations(
    file: UploadFile = File(..., description="CSV or JSON location file"),
    country: str = Form("NP", description="Country code, e.g. NP"),
    format: str = Form("auto", description="File format: 'csv', 'json', or 'auto' (detect from filename)"),
    max_level: int = Form(3, description="Skip nodes deeper than this level (1–3)"),
    dry_run: bool = Form(False, description="Parse only — do not write to DB"),
    # CSV-specific column mapping (optional overrides)
    lang_prefix: str = Form("name_", description="CSV language column prefix (default: name_)"),
    db: Session = Depends(get_db),
    _admin: CurrentUser = Depends(require_admin),
):
    """
    Upload a location file and upsert into ticketing.locations + location_translations.

    **CSV format** — flat rows, one location per line:
    ```
    location_code,level_number,parent_location_code,source_id,name_en,name_ne
    P1,1,,1,Koshi Province,कोशी
    P1_JHA,2,P1,4,Jhapa,झापा
    ```
    Download the template from `GET /locations/import/template.csv`.

    **JSON format** — nested province → district → municipality (matches en_cleaned.json):
    ```json
    [{"id": 1, "name": "Province", "districts": [...]}]
    ```
    Download the template from `GET /locations/import/template.json`.

    Both formats are **idempotent** (ON CONFLICT DO UPDATE).
    Only `super_admin` may use this endpoint.
    """
    # Validate country exists
    from ticketing.models.country import Country
    if not db.get(Country, country):
        raise HTTPException(status_code=422, detail=f"Country '{country}' not found in ticketing.countries")

    # Read uploaded file
    raw_bytes = await file.read()
    filename = file.filename or ""

    # Determine format
    fmt = format.lower()
    if fmt == "auto":
        if filename.endswith(".json"):
            fmt = "json"
        elif filename.endswith(".csv"):
            fmt = "csv"
        else:
            # Try to detect by content
            stripped = raw_bytes.lstrip()
            fmt = "json" if stripped.startswith(b"[") or stripped.startswith(b"{") else "csv"

    from ticketing.seed.location_import_core import parse_csv, parse_json, upsert_locations

    try:
        if fmt == "json":
            en_data = json.loads(raw_bytes.decode("utf-8"))
            if not isinstance(en_data, list):
                raise ValueError("JSON must be a top-level array of province objects")
            location_rows, trans_rows = parse_json(en_data, {}, country, max_level)
        else:
            content = raw_bytes.decode("utf-8-sig")
            location_rows, trans_rows = parse_csv(
                content,
                country_default=country,
                lang_prefix=lang_prefix,
                max_level=max_level,
            )
    except (json.JSONDecodeError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=f"File parse error: {exc}")

    if not location_rows:
        raise HTTPException(status_code=422, detail="No valid location rows found in uploaded file")

    if dry_run:
        return ImportResult(
            country=country,
            format=fmt,
            locations_upserted=len(location_rows),
            translations_upserted=len(trans_rows),
            dry_run=True,
        )

    try:
        counts = upsert_locations(location_rows, trans_rows, db)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"DB write failed: {exc}") from exc

    return ImportResult(
        country=country,
        format=fmt,
        locations_upserted=counts["locations"],
        translations_upserted=counts["translations"],
        dry_run=False,
    )


# ── Locations ─────────────────────────────────────────────────────────────────

@router.get("/locations", response_model=list[LocationResponse])
def list_locations(
    country: str | None = Query(None, description="Filter by country_code, e.g. NP"),
    level: int | None = Query(None, description="Filter by level_number (1=Province, 2=District, 3=Municipality)"),
    parent: str | None = Query(None, description="Filter by parent_location_code"),
    q: str | None = Query(None, description="Search by English name (case-insensitive substring)"),
    active_only: bool = Query(True, description="Only return is_active=true nodes"),
    limit: int = Query(500, le=2000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    Browse the location tree with optional filters.
    Returns locations with their translations.
    """
    stmt = (
        select(Location)
        .options(selectinload(Location.translations))
        .order_by(Location.country_code, Location.level_number, Location.location_code)
    )
    if country:
        stmt = stmt.where(Location.country_code == country)
    if level is not None:
        stmt = stmt.where(Location.level_number == level)
    if parent:
        stmt = stmt.where(Location.parent_location_code == parent)
    if active_only:
        stmt = stmt.where(Location.is_active.is_(True))
    if q:
        # Search English name OR location_code (outerjoin so code-only matches still work)
        stmt = (
            stmt
            .outerjoin(
                LocationTranslation,
                (LocationTranslation.location_code == Location.location_code) &
                (LocationTranslation.lang_code == "en"),
            )
            .where(
                or_(
                    LocationTranslation.name.ilike(f"%{q}%"),
                    Location.location_code.ilike(f"%{q}%"),
                )
            )
        )
    stmt = stmt.offset(offset).limit(limit)
    rows = db.execute(stmt).scalars().all()
    return rows


@router.get("/locations/{location_code}", response_model=LocationResponse)
def get_location(location_code: str, db: Session = Depends(get_db)):
    """Get a single location node with all translations."""
    row = db.execute(
        select(Location)
        .options(selectinload(Location.translations))
        .where(Location.location_code == location_code)
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail=f"Location '{location_code}' not found")
    return row


# ── Projects ──────────────────────────────────────────────────────────────────

def _validate_project_workflow(
    db: Session,
    workflow_id: str | None,
    *,
    expected_type: str,
) -> None:
    if workflow_id is None:
        return
    from ticketing.models.workflow import WorkflowDefinition

    wf = db.get(WorkflowDefinition, workflow_id)
    if not wf:
        raise HTTPException(status_code=422, detail=f"Workflow '{workflow_id}' not found")
    if wf.is_template:
        raise HTTPException(status_code=422, detail="Templates cannot be assigned to a project")
    actual = (wf.workflow_type or "").lower()
    if actual != expected_type.lower():
        raise HTTPException(
            status_code=422,
            detail=f"Workflow must be type '{expected_type}', got '{wf.workflow_type}'",
        )


def _project_to_response(p: Project, db: Session) -> dict:
    slots = [
        ProjectWorkflowItem(**pw_svc.project_workflow_to_dict(link, db))
        for link in (p.workflow_links or [])
    ]
    return {
        "project_id":    p.project_id,
        "country_code":  p.country_code,
        "short_code":    p.short_code,
        "name":          p.name,
        "description":   p.description,
        "is_active":     p.is_active,
        "project_type_key": p.project_type_key,
        "standard_workflow_id": p.standard_workflow_id,
        "seah_workflow_id": p.seah_workflow_id,
        "implementing_agency_org_id": p.implementing_agency_org_id,
        "donor_org_ids": [d.organization_id for d in (p.donors or [])],
        "workflow_slots": slots,
        "officer_messaging": p.officer_messaging or msg_svc.default_officer_messaging(),
        "created_at":    p.created_at,
        "updated_at":    p.updated_at,
        "organizations": [
            {"organization_id": po.organization_id, "org_role": po.org_role}
            for po in p.organizations
        ],
        "location_codes": [pl.location_code for pl in p.locations],
    }


def _load_project(db: Session, project_id: str) -> Project | None:
    return db.execute(
        select(Project)
        .options(
            selectinload(Project.organizations),
            selectinload(Project.locations),
            selectinload(Project.workflow_links),
        )
        .where(Project.project_id == project_id)
    ).scalar_one_or_none()


@router.get("/projects", response_model=list[ProjectResponse])
def list_projects(
    country: str | None = Query(None),
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
):
    """List all projects with linked org IDs and location codes."""
    stmt = (
        select(Project)
        .options(
            selectinload(Project.organizations),
            selectinload(Project.locations),
            selectinload(Project.workflow_links),
        )
        .order_by(Project.country_code, Project.short_code)
    )
    if country:
        stmt = stmt.where(Project.country_code == country)
    if active_only:
        stmt = stmt.where(Project.is_active.is_(True))
    rows = db.execute(stmt).scalars().all()
    return [_project_to_response(p, db) for p in rows]


@router.post("/projects", response_model=ProjectResponse, status_code=201)
def create_project(
    body: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
):
    """Create a new project. Standard-track country admin or super_admin."""
    require_settings_write(current_user, SettingsAction.CREATE_PROJECT)
    # Creating a project is a standard-track structural action: a SEAH-only
    # org_admin is unauthorized and must get 403 here, before body/country/
    # go-live validation can turn the request into a 422.
    require_track_for_mutation(current_user, "standard")

    # Validate country exists
    if not db.get(Country, body.country_code):
        raise HTTPException(status_code=422, detail=f"Country '{body.country_code}' not found")

    # Check short_code uniqueness
    existing = db.execute(
        select(Project).where(Project.short_code == body.short_code)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail=f"Project short_code '{body.short_code}' already exists")

    typed = bool(body.project_type_key)
    default_active = False if typed else True
    is_active = body.is_active if body.is_active is not None else default_active

    now = _now()
    project = Project(
        project_id=str(uuid.uuid4()),
        country_code=body.country_code,
        short_code=body.short_code,
        name=body.name,
        description=body.description,
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )
    if body.implementing_agency_org_id:
        try:
            donor_guardrail_svc.validate_implementing_agency(db, body.implementing_agency_org_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        project.implementing_agency_org_id = body.implementing_agency_org_id

    db.add(project)
    db.flush()

    if body.project_type_key:
        try:
            types_svc.instantiate_project_from_type(db, project, body.project_type_key)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    else:
        actor_roles_svc.seed_project_actor_roles(db, project.project_id)

    if is_active:
        report = go_live_svc.evaluate_go_live(db, project.project_id)
        if not report.can_activate:
            raise HTTPException(
                status_code=422,
                detail=go_live_svc.activation_block_message(report) or "Cannot activate project yet",
            )

    db.commit()
    db.refresh(project)

    p = _load_project(db, project.project_id)
    assert p is not None
    return _project_to_response(p, db)


@router.get("/projects/{project_id}/go-live", response_model=GoLiveReportResponse)
def get_project_go_live(project_id: str, db: Session = Depends(get_db)):
    """Go-live readiness checklist for a project."""
    if not db.get(Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    report = go_live_svc.evaluate_go_live(db, project_id)
    return GoLiveReportResponse(
        checks=[
            GoLiveCheckResponse(
                id=c.id,
                label=c.label,
                group=c.group,
                severity=c.severity,
                status=c.status,
                message=c.message,
                section=c.section,
            )
            for c in report.checks
        ],
        can_activate=report.can_activate,
        can_accept_tickets=report.can_accept_tickets,
        summary=report.summary,
    )


@router.get("/projects/{project_id}/messaging", response_model=ProjectMessagingResponse)
def get_project_messaging(project_id: str, db: Session = Depends(get_db)):
    """Officer SMS/WhatsApp config for a project plus computed max workflow levels."""
    config = msg_svc.get_officer_messaging(db, project_id)
    max_levels = msg_svc.max_workflow_levels_for_project(db, project_id)
    return ProjectMessagingResponse(
        sms_enabled=config.sms_enabled,
        sms_levels=config.sms_levels,
        whatsapp_levels=config.whatsapp_levels,
        max_levels=max_levels,
    )


@router.patch("/projects/{project_id}/messaging", response_model=ProjectMessagingResponse)
def patch_project_messaging(
    project_id: str,
    body: ProjectMessagingPatch,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
):
    """Update officer messaging config. Country admin or super admin only."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    msg_svc.require_project_messaging_edit(current_user, project)
    config = msg_svc.update_officer_messaging(db, project_id, body)
    project.updated_at = _now()
    db.commit()
    max_levels = msg_svc.max_workflow_levels_for_project(db, project_id)
    return ProjectMessagingResponse(
        sms_enabled=config.sms_enabled,
        sms_levels=config.sms_levels,
        whatsapp_levels=config.whatsapp_levels,
        max_levels=max_levels,
    )


@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, db: Session = Depends(get_db)):
    """Get a single project with all org and location links."""
    p = _load_project(db, project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return _project_to_response(p, db)


@router.get("/projects/{project_id}/workflows", response_model=list[ProjectWorkflowItem])
def list_project_workflow_slots(project_id: str, db: Session = Depends(get_db)):
    """Workflow streams linked on this project (safeguards, hazards, CA, SEAH, custom)."""
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    rows = pw_svc.list_project_workflows(db, project_id)
    return [ProjectWorkflowItem(**pw_svc.project_workflow_to_dict(r, db)) for r in rows]


@router.put("/projects/{project_id}/workflows", response_model=list[ProjectWorkflowItem])
def replace_project_workflow_slots(
    project_id: str,
    body: ProjectWorkflowsReplace,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
):
    """Replace all workflow bindings on a project."""
    p = _load_project(db, project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    from ticketing.models.workflow import WorkflowDefinition

    for item in body.items:
        wf = db.get(WorkflowDefinition, item.workflow_id)
        wtype = (wf.workflow_type if wf else "standard") or "standard"
        if not can_assign_project_workflow(current_user, wtype):
            raise HTTPException(
                status_code=403,
                detail=f"Not allowed to assign workflow '{item.display_label}'",
            )

    rows = pw_svc.replace_project_workflows(
        db,
        p,
        [item.model_dump() for item in body.items],
    )
    p.updated_at = _now()
    db.commit()
    db.refresh(p)
    return [ProjectWorkflowItem(**pw_svc.project_workflow_to_dict(r, db)) for r in rows]


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: str,
    body: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
):
    """Update project metadata. Admin only."""

    p = _load_project(db, project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    if body.name is not None:
        p.name = body.name
    if body.short_code is not None:
        try:
            entity_codes_svc.rename_project_short_code(db, p, body.short_code)
        except ValueError as exc:
            msg = str(exc)
            if "already in use" in msg:
                raise HTTPException(status_code=409, detail=msg) from exc
            raise HTTPException(status_code=422, detail=msg) from exc
    if body.description is not None:
        p.description = body.description
    if "implementing_agency_org_id" in body.model_fields_set:
        if body.implementing_agency_org_id:
            try:
                donor_guardrail_svc.validate_implementing_agency(
                    db, body.implementing_agency_org_id
                )
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
        p.implementing_agency_org_id = body.implementing_agency_org_id
        db.flush()
    if body.is_active is not None:
        if body.is_active and not p.is_active:
            report = go_live_svc.evaluate_go_live(db, project_id)
            if not report.can_activate:
                raise HTTPException(
                    status_code=422,
                    detail=go_live_svc.activation_block_message(report) or "Cannot activate project yet",
                )
        p.is_active = body.is_active
    if "standard_workflow_id" in body.model_fields_set or "seah_workflow_id" in body.model_fields_set:
        bindings = [
            pw_svc.project_workflow_to_dict(row, db)
            for row in pw_svc.list_project_workflows(db, project_id)
        ]
        if "standard_workflow_id" in body.model_fields_set:
            if not can_assign_project_workflow(current_user, "standard"):
                raise HTTPException(status_code=403, detail="Not allowed to edit default workflow")
            _validate_project_workflow(db, body.standard_workflow_id, expected_type="standard")
            updated = False
            for b in bindings:
                if b.get("is_default"):
                    b["workflow_id"] = body.standard_workflow_id
                    updated = True
            if body.standard_workflow_id and not updated:
                bindings.append(
                    {
                        "display_label": "Safeguards GRM",
                        "workflow_id": body.standard_workflow_id,
                        "is_default": True,
                        "classifications": [],
                        "intake_route": "new_grievance",
                        "sort_order": 10,
                    }
                )
        if "seah_workflow_id" in body.model_fields_set:
            if not can_assign_project_workflow(current_user, "seah"):
                raise HTTPException(status_code=403, detail="Not allowed to edit SEAH workflow")
            _validate_project_workflow(db, body.seah_workflow_id, expected_type="seah")
            if body.seah_workflow_id:
                seah_row = next(
                    (b for b in bindings if (b.get("workflow_track") or "") == "seah"),
                    None,
                )
                if seah_row:
                    seah_row["workflow_id"] = body.seah_workflow_id
                else:
                    bindings.append(
                        {
                            "display_label": "SEAH",
                            "workflow_id": body.seah_workflow_id,
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
            else:
                bindings = [b for b in bindings if (b.get("workflow_track") or "") != "seah"]
        if bindings:
            pw_svc.replace_project_workflows(db, p, bindings)
    p.updated_at = _now()

    db.commit()
    p = _load_project(db, project_id)
    assert p is not None
    return _project_to_response(p, db)


@router.delete("/projects/{project_id}", status_code=204, summary="Delete project (admin)")
def delete_project(
    project_id: str,
    db: Session = Depends(get_db),
    _admin: CurrentUser = Depends(require_admin),
) -> None:
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    ticket_count = db.scalar(
        select(func.count()).select_from(Ticket).where(Ticket.project_id == project_id)
    ) or 0
    if ticket_count:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete: {ticket_count} ticket(s) reference this project.",
        )

    db.delete(p)
    db.commit()


# ── Project ↔ Organizations ───────────────────────────────────────────────────

@router.get("/projects/{project_id}/organizations", response_model=list[ProjectOrgItem])
def list_project_organizations(project_id: str, db: Session = Depends(get_db)):
    """List organizations linked to a project, with their roles."""
    if not db.get(Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    rows = db.execute(
        select(ProjectOrganization).where(ProjectOrganization.project_id == project_id)
    ).scalars().all()
    return [{"organization_id": r.organization_id, "org_role": r.org_role} for r in rows]


class OrgRoleBody(BaseModel):
    org_role: str | None = None


@router.post("/projects/{project_id}/organizations/{organization_id}", status_code=201,
             response_model=ProjectOrgItem)
def add_project_organization(
    project_id: str,
    organization_id: str,
    body: OrgRoleBody = OrgRoleBody(),
    db: Session = Depends(get_db),
    _admin: CurrentUser = Depends(require_admin),
):
    """Link an organization to a project with an optional role. Admin only."""
    if not db.get(Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    if not db.get(Organization, organization_id):
        raise HTTPException(status_code=404, detail=f"Organization '{organization_id}' not found")

    existing = db.execute(
        select(ProjectOrganization)
        .where(
            ProjectOrganization.project_id == project_id,
            ProjectOrganization.organization_id == organization_id,
        )
    ).scalar_one_or_none()
    try:
        actor_roles_svc.validate_org_role_for_project(db, project_id, body.org_role)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if existing:
        # Allow updating the role on an existing link
        existing.org_role = body.org_role
        db.commit()
        return {"organization_id": organization_id, "org_role": existing.org_role}

    po = ProjectOrganization(
        project_id=project_id,
        organization_id=organization_id,
        org_role=body.org_role,
    )
    db.add(po)
    db.commit()
    return {"organization_id": organization_id, "org_role": po.org_role}


@router.patch("/projects/{project_id}/organizations/{organization_id}",
              response_model=ProjectOrgItem)
def update_project_organization_role(
    project_id: str,
    organization_id: str,
    body: OrgRoleBody,
    db: Session = Depends(get_db),
    _admin: CurrentUser = Depends(require_admin),
):
    """Update the role of an already-linked organization. Admin only."""
    row = db.execute(
        select(ProjectOrganization)
        .where(
            ProjectOrganization.project_id == project_id,
            ProjectOrganization.organization_id == organization_id,
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Organization not linked to this project")
    try:
        actor_roles_svc.validate_org_role_for_project(db, project_id, body.org_role)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    row.org_role = body.org_role
    db.commit()
    return {"organization_id": organization_id, "org_role": row.org_role}


# ── Project donors (doc 13 / DECISION 2026-07-10 §3) ──────────────────────────

class DonorItem(BaseModel):
    organization_id: str
    name: str | None = None


@router.get("/projects/{project_id}/donors", response_model=list[DonorItem])
def list_project_donors(project_id: str, db: Session = Depends(get_db)):
    """Donor organizations funding this project (category ``donor``)."""
    if not db.get(Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    rows = db.execute(
        select(ProjectDonor).where(ProjectDonor.project_id == project_id)
    ).scalars().all()
    out: list[DonorItem] = []
    for r in rows:
        org = db.get(Organization, r.organization_id)
        out.append(DonorItem(organization_id=r.organization_id, name=org.name if org else None))
    return out


@router.post("/projects/{project_id}/donors/{organization_id}", status_code=201,
             response_model=DonorItem)
def add_project_donor(
    project_id: str,
    organization_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
):
    """Add a donor to a project (doc 13 §3). Standard-track project mutation.

    Auto-populates the final standard step's "Kept informed" cast with the donor tiers
    (the admin may later trim to ≥1) so the go-live donor guardrail is satisfiable and
    donor staff are notified on final escalation. **SEAH-suppressed** at runtime.
    """
    require_settings_write(current_user, SettingsAction.MANAGE_PROJECT)
    require_track_for_mutation(current_user, "standard")

    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        donor_guardrail_svc.validate_donor_org(db, organization_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    existing = db.get(ProjectDonor, (project_id, organization_id))
    if existing is None:
        db.add(ProjectDonor(project_id=project_id, organization_id=organization_id))
        db.flush()
    # Auto-populate the last standard step's informed cast (idempotent).
    donor_guardrail_svc.apply_donor_informed_defaults(db, project)
    db.commit()
    org = db.get(Organization, organization_id)
    return DonorItem(organization_id=organization_id, name=org.name if org else None)


@router.delete("/projects/{project_id}/donors/{organization_id}", status_code=204)
def remove_project_donor(
    project_id: str,
    organization_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
):
    """Remove a donor from a project. Leaves the donor roles in the workflow cast (an
    admin trims those in the workflow editor) — removing the donor only drops the
    go-live guardrail requirement."""
    require_settings_write(current_user, SettingsAction.MANAGE_PROJECT)
    require_track_for_mutation(current_user, "standard")

    if not db.get(Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    row = db.get(ProjectDonor, (project_id, organization_id))
    if row is not None:
        db.delete(row)
        db.commit()
    return None


# ── Project actor role vocabulary ─────────────────────────────────────────────

class ActorRoleItem(BaseModel):
    key: str
    label: str
    description: str = ""
    sort_order: int = 0


class ActorRolesReplace(BaseModel):
    roles: list[ActorRoleItem]


@router.get("/projects/{project_id}/actor-roles", response_model=list[ActorRoleItem])
def list_project_actor_roles(project_id: str, db: Session = Depends(get_db)):
    """Role vocabulary for this project (donor, CSC, contractor, etc.)."""
    if not db.get(Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    rows = actor_roles_svc.list_project_actor_roles(db, project_id)
    if not rows:
        rows = actor_roles_svc.seed_project_actor_roles(db, project_id)
        db.commit()
    return actor_roles_svc.actor_roles_to_api(rows)


@router.put("/projects/{project_id}/actor-roles", response_model=list[ActorRoleItem])
def replace_project_actor_roles(
    project_id: str,
    body: ActorRolesReplace,
    db: Session = Depends(get_db),
    admin: CurrentUser = Depends(require_admin),
):
    """Replace the full role vocabulary for a project. Super admin only when project has a type."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.project_type_key and not (
        admin.is_super_admin or admin.is_org_admin()
    ):
        raise HTTPException(
            status_code=403,
            detail="Actor role keys are defined by the project type; admin only",
        )
    try:
        rows = actor_roles_svc.replace_project_actor_roles(
            db,
            project_id,
            [r.model_dump() for r in body.roles],
        )
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return actor_roles_svc.actor_roles_to_api(rows)


@router.delete("/projects/{project_id}/organizations/{organization_id}", status_code=204)
def remove_project_organization(
    project_id: str,
    organization_id: str,
    db: Session = Depends(get_db),
    _admin: CurrentUser = Depends(require_admin),
):
    """Unlink an organization from a project. Admin only."""

    row = db.execute(
        select(ProjectOrganization)
        .where(
            ProjectOrganization.project_id == project_id,
            ProjectOrganization.organization_id == organization_id,
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Link not found")
    db.delete(row)
    db.commit()


# ── Project ↔ Locations ───────────────────────────────────────────────────────

@router.get("/projects/{project_id}/locations")
def list_project_locations(
    project_id: str,
    with_details: bool = Query(False, description="Include full location + translations"),
    db: Session = Depends(get_db),
):
    """List locations linked to a project."""
    if not db.get(Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    if with_details:
        stmt = (
            select(Location)
            .options(selectinload(Location.translations))
            .join(ProjectLocation, ProjectLocation.location_code == Location.location_code)
            .where(ProjectLocation.project_id == project_id)
            .order_by(Location.level_number, Location.location_code)
        )
        rows = db.execute(stmt).scalars().all()
        return rows  # LocationResponse shape
    else:
        rows = db.execute(
            select(ProjectLocation).where(ProjectLocation.project_id == project_id)
        ).scalars().all()
        return [{"project_id": r.project_id, "location_code": r.location_code} for r in rows]


@router.post("/projects/{project_id}/locations/{location_code}", status_code=201)
def add_project_location(
    project_id: str,
    location_code: str,
    db: Session = Depends(get_db),
    _admin: CurrentUser = Depends(require_admin),
):
    """Link a location node to a project. Admin only."""

    if not db.get(Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    if not db.get(Location, location_code):
        raise HTTPException(status_code=404, detail=f"Location '{location_code}' not found")

    existing = db.execute(
        select(ProjectLocation)
        .where(
            ProjectLocation.project_id == project_id,
            ProjectLocation.location_code == location_code,
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Location already linked to this project")

    db.add(ProjectLocation(project_id=project_id, location_code=location_code))
    db.commit()
    return {"project_id": project_id, "location_code": location_code}


@router.delete("/projects/{project_id}/locations/{location_code}", status_code=204)
def remove_project_location(
    project_id: str,
    location_code: str,
    db: Session = Depends(get_db),
    _admin: CurrentUser = Depends(require_admin),
):
    """Unlink a location from a project. Admin only."""

    row = db.execute(
        select(ProjectLocation)
        .where(
            ProjectLocation.project_id == project_id,
            ProjectLocation.location_code == location_code,
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Link not found")
    db.delete(row)
    db.commit()


# ── Project packages ──────────────────────────────────────────────────────────

class PackageOrgItem(BaseModel):
    organization_id: str
    org_role: str


class PackageResponse(BaseModel):
    package_id:        str
    project_id:        str
    package_code:      str
    name:              str
    description:       str | None
    organizations:     list[PackageOrgItem] = []
    is_active:         bool
    location_codes:    list[str] = []
    created_at:        datetime
    updated_at:        datetime

    model_config = {"from_attributes": True}


class PackageCreate(BaseModel):
    package_code:      str | None = Field(None, max_length=8)
    name:              str
    description:       str | None = None
    is_active:         bool = True

    @field_validator("package_code", mode="before")
    @classmethod
    def _normalize_package_code(cls, v: object) -> str | None:
        if v is None or (isinstance(v, str) and not str(v).strip()):
            return None
        try:
            return validate_entity_code(str(v), field="Package code")
        except EntityCodeError as exc:
            raise ValueError(str(exc)) from exc


class PackageUpdate(BaseModel):
    package_code:      str | None = Field(None, max_length=8)
    name:              str | None = None
    description:       str | None = None
    is_active:         bool | None = None

    @field_validator("package_code", mode="before")
    @classmethod
    def _normalize_package_code(cls, v: object) -> str | None:
        if v is None or (isinstance(v, str) and not str(v).strip()):
            return None
        try:
            return validate_entity_code(str(v), field="Package code")
        except EntityCodeError as exc:
            raise ValueError(str(exc)) from exc


def _package_to_dict(pkg: ProjectPackage) -> dict:
    return {
        "package_id":        pkg.package_id,
        "project_id":        pkg.project_id,
        "package_code":      pkg.package_code,
        "name":              pkg.name,
        "description":       pkg.description,
        "organizations":     [
            {"organization_id": po.organization_id, "org_role": po.org_role}
            for po in (pkg.organizations or [])
        ],
        "is_active":         pkg.is_active,
        "location_codes":    [pl.location_code for pl in pkg.locations],
        "created_at":        pkg.created_at,
        "updated_at":        pkg.updated_at,
    }


def _get_package_or_404(db: Session, project_id: str, package_id: str) -> ProjectPackage:
    pkg = db.execute(
        select(ProjectPackage)
        .options(
            selectinload(ProjectPackage.locations),
            selectinload(ProjectPackage.organizations),
        )
        .where(
            ProjectPackage.package_id == package_id,
            ProjectPackage.project_id == project_id,
        )
    ).scalar_one_or_none()
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")
    return pkg


@router.get("/projects/{project_id}/packages", response_model=list[PackageResponse])
def list_packages(project_id: str, db: Session = Depends(get_db)):
    """List all packages for a project, ordered by package_code."""
    if not db.get(Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    pkgs = db.execute(
        select(ProjectPackage)
        .options(
            selectinload(ProjectPackage.locations),
            selectinload(ProjectPackage.organizations),
        )
        .where(ProjectPackage.project_id == project_id)
        .order_by(ProjectPackage.package_code)
    ).scalars().all()
    return [_package_to_dict(p) for p in pkgs]


@router.post("/projects/{project_id}/packages", response_model=PackageResponse, status_code=201)
def create_package(
    project_id: str,
    body: PackageCreate,
    db: Session = Depends(get_db),
    _admin: CurrentUser = Depends(require_admin),
):
    """Create a package within a project. Admin only."""
    if not db.get(Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    package_code = body.package_code or entity_codes_svc.next_package_code(db, project_id)

    existing = db.execute(
        select(ProjectPackage).where(
            ProjectPackage.project_id == project_id,
            ProjectPackage.package_code == package_code,
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail=f"Package '{package_code}' already exists in this project")

    pkg = ProjectPackage(
        project_id=project_id,
        package_code=package_code,
        name=body.name,
        description=body.description,
        is_active=body.is_active,
    )
    db.add(pkg)
    db.flush()
    db.refresh(pkg, ["locations", "organizations"])
    db.commit()
    return _package_to_dict(pkg)


@router.patch("/projects/{project_id}/packages/{package_id}", response_model=PackageResponse)
def update_package(
    project_id: str,
    package_id: str,
    body: PackageUpdate,
    db: Session = Depends(get_db),
    _admin: CurrentUser = Depends(require_admin),
):
    """Update package metadata. Admin only."""
    pkg = _get_package_or_404(db, project_id, package_id)

    if body.package_code is not None and body.package_code != pkg.package_code:
        conflict = db.execute(
            select(ProjectPackage).where(
                ProjectPackage.project_id == project_id,
                ProjectPackage.package_code == body.package_code,
                ProjectPackage.package_id != package_id,
            )
        ).scalar_one_or_none()
        if conflict:
            raise HTTPException(
                status_code=409,
                detail=f"Package '{body.package_code}' already exists in this project",
            )
        pkg.package_code = body.package_code
    if body.name              is not None: pkg.name              = body.name
    if body.description       is not None: pkg.description       = body.description
    if body.is_active         is not None: pkg.is_active         = body.is_active
    pkg.updated_at = _now()
    db.commit()
    db.refresh(pkg)
    return _package_to_dict(pkg)


@router.post("/projects/{project_id}/packages/{package_id}/locations/{location_code}",
             status_code=201)
def add_package_location(
    project_id: str,
    package_id: str,
    location_code: str,
    db: Session = Depends(get_db),
    _admin: CurrentUser = Depends(require_admin),
):
    """Link a district/location to a package. Admin only."""
    pkg = db.execute(
        select(ProjectPackage).where(
            ProjectPackage.package_id == package_id,
            ProjectPackage.project_id == project_id,
        )
    ).scalar_one_or_none()
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")
    if not db.get(Location, location_code):
        raise HTTPException(status_code=404, detail=f"Location '{location_code}' not found")

    existing = db.execute(
        select(PackageLocation).where(
            PackageLocation.package_id == package_id,
            PackageLocation.location_code == location_code,
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Location already linked to this package")

    db.add(PackageLocation(package_id=package_id, location_code=location_code))
    db.commit()
    return {"package_id": package_id, "location_code": location_code}


@router.delete("/projects/{project_id}/packages/{package_id}/locations/{location_code}",
               status_code=204)
def remove_package_location(
    project_id: str,
    package_id: str,
    location_code: str,
    db: Session = Depends(get_db),
    _admin: CurrentUser = Depends(require_admin),
):
    """Unlink a location from a package. Admin only."""
    row = db.execute(
        select(PackageLocation).where(
            PackageLocation.package_id == package_id,
            PackageLocation.location_code == location_code,
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Package location link not found")
    db.delete(row)
    db.commit()


# ── Package ↔ Organizations (package-level actors) ───────────────────────────

class PackageOrgRoleBody(BaseModel):
    org_role: str = Field(..., min_length=1, max_length=64)


@router.post(
    "/projects/{project_id}/packages/{package_id}/organizations/{organization_id}",
    response_model=PackageOrgItem,
    status_code=201,
)
def add_package_organization(
    project_id: str,
    package_id: str,
    organization_id: str,
    body: PackageOrgRoleBody,
    db: Session = Depends(get_db),
    _admin: CurrentUser = Depends(require_admin),
):
    """Assign an organization + role to a package (overrides project-wide for this lot)."""
    _get_package_or_404(db, project_id, package_id)
    if not db.get(Organization, organization_id):
        raise HTTPException(status_code=404, detail=f"Organization '{organization_id}' not found")
    try:
        actor_roles_svc.validate_org_role_for_project(db, project_id, body.org_role)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    existing = db.execute(
        select(PackageOrganization).where(
            PackageOrganization.package_id == package_id,
            PackageOrganization.organization_id == organization_id,
            PackageOrganization.org_role == body.org_role,
        )
    ).scalar_one_or_none()
    if existing:
        return {"organization_id": organization_id, "org_role": body.org_role}

    row = PackageOrganization(
        package_id=package_id,
        organization_id=organization_id,
        org_role=body.org_role,
    )
    db.add(row)
    db.commit()
    return {"organization_id": organization_id, "org_role": body.org_role}


@router.delete(
    "/projects/{project_id}/packages/{package_id}/organizations/{organization_id}/{org_role}",
    status_code=204,
)
def remove_package_organization(
    project_id: str,
    package_id: str,
    organization_id: str,
    org_role: str,
    db: Session = Depends(get_db),
    _admin: CurrentUser = Depends(require_admin),
):
    """Remove a package-level actor assignment."""
    _get_package_or_404(db, project_id, package_id)
    row = db.execute(
        select(PackageOrganization).where(
            PackageOrganization.package_id == package_id,
            PackageOrganization.organization_id == organization_id,
            PackageOrganization.org_role == org_role,
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Package actor not found")
    db.delete(row)
    db.commit()
