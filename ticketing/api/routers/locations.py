"""
Locations, Countries, Organizations, and Projects — read + admin CRUD endpoints.

Endpoints:
    GET    /organizations                      list organizations
    POST   /organizations                      create organization (admin)
    PATCH  /organizations/{id}                 update organization (admin)
    GET  /countries                           list countries
    GET  /locations?country=NP&level=2&parent=NP_P1&q=bira   browse tree
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
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from ticketing.api.dependencies import CurrentUser, require_admin
from ticketing.models.base import get_db
from ticketing.models.country import Country, Location, LocationLevelDef, LocationTranslation
from ticketing.models.organization import Organization
from ticketing.utils.organization_identifier import (
    allocate_unique_organization_id,
    suggested_organization_id,
)
from ticketing.models.package import PackageLocation, ProjectPackage
from ticketing.models.project import Project, ProjectLocation, ProjectOrganization

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
    short_code: str   = Field(..., max_length=64)
    name: str
    description: str | None = None
    is_active: bool = True


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None


class ProjectOrgItem(BaseModel):
    """Organization linked to a project, with its role in that project."""
    organization_id: str
    org_role: str | None = None

    model_config = {"from_attributes": True}


class ProjectResponse(BaseModel):
    project_id: str
    country_code: str
    short_code: str
    name: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    organizations: list[ProjectOrgItem] = []
    location_codes: list[str] = []

    model_config = {"from_attributes": True}


# ── Organizations ─────────────────────────────────────────────────────────────

class OrganizationResponse(BaseModel):
    organization_id: str
    name: str
    country_code: str | None
    is_active: bool
    default_language: str = "ne"
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


class OrganizationUpdate(BaseModel):
    name: str | None = None
    country_code: str | None = None
    is_active: bool | None = None
    default_language: str | None = None


@router.get("/organizations", response_model=list[OrganizationResponse])
def list_organizations(
    country: str | None = Query(None),
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
):
    """List all organizations."""
    stmt = select(Organization).order_by(Organization.organization_id)
    if country:
        stmt = stmt.where(Organization.country_code == country)
    if active_only:
        stmt = stmt.where(Organization.is_active.is_(True))
    return db.execute(stmt).scalars().all()


@router.post("/organizations", response_model=OrganizationResponse, status_code=201,
             summary="Create an organization (admin)")
def create_organization(
    body: OrganizationCreate,
    db: Session = Depends(get_db),
    _admin: CurrentUser = Depends(require_admin),
):
    """Create a new organization. Admin only."""
    name_clean = body.name.strip()
    if not name_clean:
        raise HTTPException(status_code=400, detail="Name is required")

    raw = body.organization_id.strip() if body.organization_id else ""
    if raw:
        org_id = "".join(c for c in raw.upper() if c.isalnum() or c == "_")
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
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@router.patch("/organizations/{organization_id}", response_model=OrganizationResponse,
              summary="Update an organization (admin)")
def update_organization(
    organization_id: str,
    body: OrganizationUpdate,
    db: Session = Depends(get_db),
    _admin: CurrentUser = Depends(require_admin),
):
    """Update organization name, country, or active status. Admin only."""
    org = db.get(Organization, organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    if body.name is not None:
        org.name = body.name.strip()
    if body.country_code is not None:
        org.country_code = body.country_code or None
    if body.is_active is not None:
        org.is_active = body.is_active
    if body.default_language is not None:
        org.default_language = body.default_language
    org.updated_at = _now()
    db.commit()
    db.refresh(org)
    return org


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
      - location_code        unique code, e.g. NP_P1 / NP_D001 / NP_M0001
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
    NP_P1,1,,1,Koshi Province,कोशी
    NP_D004,2,NP_P1,4,Jhapa,झापा
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

def _project_to_response(p: Project) -> dict:
    return {
        "project_id":    p.project_id,
        "country_code":  p.country_code,
        "short_code":    p.short_code,
        "name":          p.name,
        "description":   p.description,
        "is_active":     p.is_active,
        "created_at":    p.created_at,
        "updated_at":    p.updated_at,
        "organizations": [
            {"organization_id": po.organization_id, "org_role": po.org_role}
            for po in p.organizations
        ],
        "location_codes": [pl.location_code for pl in p.locations],
    }


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
        )
        .order_by(Project.country_code, Project.short_code)
    )
    if country:
        stmt = stmt.where(Project.country_code == country)
    if active_only:
        stmt = stmt.where(Project.is_active.is_(True))
    rows = db.execute(stmt).scalars().all()
    return [_project_to_response(p) for p in rows]


@router.post("/projects", response_model=ProjectResponse, status_code=201)
def create_project(
    body: ProjectCreate,
    db: Session = Depends(get_db),
    _admin: CurrentUser = Depends(require_admin),
):
    """Create a new project. Admin only."""

    # Validate country exists
    if not db.get(Country, body.country_code):
        raise HTTPException(status_code=422, detail=f"Country '{body.country_code}' not found")

    # Check short_code uniqueness
    existing = db.execute(
        select(Project).where(Project.short_code == body.short_code)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail=f"Project short_code '{body.short_code}' already exists")

    now = _now()
    project = Project(
        project_id=str(uuid.uuid4()),
        country_code=body.country_code,
        short_code=body.short_code,
        name=body.name,
        description=body.description,
        is_active=body.is_active,
        created_at=now,
        updated_at=now,
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    # Reload with relationships
    p = db.execute(
        select(Project)
        .options(selectinload(Project.organizations), selectinload(Project.locations))
        .where(Project.project_id == project.project_id)
    ).scalar_one()
    return _project_to_response(p)


@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, db: Session = Depends(get_db)):
    """Get a single project with all org and location links."""
    p = db.execute(
        select(Project)
        .options(selectinload(Project.organizations), selectinload(Project.locations))
        .where(Project.project_id == project_id)
    ).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return _project_to_response(p)


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: str,
    body: ProjectUpdate,
    db: Session = Depends(get_db),
    _admin: CurrentUser = Depends(require_admin),
):
    """Update project metadata. Admin only."""

    p = db.execute(
        select(Project)
        .options(selectinload(Project.organizations), selectinload(Project.locations))
        .where(Project.project_id == project_id)
    ).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    if body.name is not None:
        p.name = body.name
    if body.description is not None:
        p.description = body.description
    if body.is_active is not None:
        p.is_active = body.is_active
    p.updated_at = _now()

    db.commit()
    db.refresh(p)
    return _project_to_response(p)


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
    row.org_role = body.org_role
    db.commit()
    return {"organization_id": organization_id, "org_role": row.org_role}


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

class PackageResponse(BaseModel):
    package_id:        str
    project_id:        str
    package_code:      str
    name:              str
    description:       str | None
    contractor_org_id: str | None
    is_active:         bool
    location_codes:    list[str] = []
    created_at:        datetime
    updated_at:        datetime

    model_config = {"from_attributes": True}


class PackageCreate(BaseModel):
    package_code:      str = Field(..., max_length=128)
    name:              str
    description:       str | None = None
    contractor_org_id: str | None = None
    is_active:         bool = True


class PackageUpdate(BaseModel):
    name:              str | None = None
    description:       str | None = None
    contractor_org_id: str | None = None
    is_active:         bool | None = None


def _package_to_dict(pkg: ProjectPackage) -> dict:
    return {
        "package_id":        pkg.package_id,
        "project_id":        pkg.project_id,
        "package_code":      pkg.package_code,
        "name":              pkg.name,
        "description":       pkg.description,
        "contractor_org_id": pkg.contractor_org_id,
        "is_active":         pkg.is_active,
        "location_codes":    [pl.location_code for pl in pkg.locations],
        "created_at":        pkg.created_at,
        "updated_at":        pkg.updated_at,
    }


@router.get("/projects/{project_id}/packages", response_model=list[PackageResponse])
def list_packages(project_id: str, db: Session = Depends(get_db)):
    """List all packages for a project, ordered by package_code."""
    if not db.get(Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    pkgs = db.execute(
        select(ProjectPackage)
        .options(selectinload(ProjectPackage.locations))
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
    if body.contractor_org_id and not db.get(Organization, body.contractor_org_id):
        raise HTTPException(status_code=404, detail=f"Organization '{body.contractor_org_id}' not found")

    existing = db.execute(
        select(ProjectPackage).where(
            ProjectPackage.project_id == project_id,
            ProjectPackage.package_code == body.package_code,
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail=f"Package '{body.package_code}' already exists in this project")

    pkg = ProjectPackage(
        project_id=project_id,
        package_code=body.package_code,
        name=body.name,
        description=body.description,
        contractor_org_id=body.contractor_org_id,
        is_active=body.is_active,
    )
    db.add(pkg)
    db.flush()
    db.refresh(pkg, ["locations"])
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
    pkg = db.execute(
        select(ProjectPackage)
        .options(selectinload(ProjectPackage.locations))
        .where(ProjectPackage.package_id == package_id,
               ProjectPackage.project_id == project_id)
    ).scalar_one_or_none()
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")

    if body.name              is not None: pkg.name              = body.name
    if body.description       is not None: pkg.description       = body.description
    if body.contractor_org_id is not None:
        if body.contractor_org_id and not db.get(Organization, body.contractor_org_id):
            raise HTTPException(status_code=404, detail=f"Organization '{body.contractor_org_id}' not found")
        pkg.contractor_org_id = body.contractor_org_id
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
