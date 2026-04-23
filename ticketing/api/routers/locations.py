"""
Locations, Countries, and Projects — read + admin CRUD endpoints.

Endpoints:
    GET  /countries                           list countries
    GET  /locations?country=NP&level=2&parent=NP_P1&q=bira   browse tree
    GET  /locations/{location_code}           single node + translations

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

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ticketing.models.base import get_db
from ticketing.models.country import Country, Location, LocationLevelDef, LocationTranslation
from ticketing.models.organization import Organization
from ticketing.models.project import Project, ProjectLocation, ProjectOrganization

router = APIRouter()

UTC = timezone.utc


def _now() -> datetime:
    return datetime.now(UTC)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_admin(x_role: str | None = None) -> None:
    """Placeholder: replace with real Cognito JWT role check in production."""
    # INTEGRATION POINT: validate Cognito JWT and check role = super_admin / local_admin
    pass


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


class ProjectResponse(BaseModel):
    project_id: str
    country_code: str
    short_code: str
    name: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    organization_ids: list[str] = []
    location_codes: list[str] = []

    model_config = {"from_attributes": True}


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
        # Join translations to search English names
        stmt = (
            stmt
            .join(LocationTranslation,
                  (LocationTranslation.location_code == Location.location_code) &
                  (LocationTranslation.lang_code == "en"))
            .where(LocationTranslation.name.ilike(f"%{q}%"))
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
        "organization_ids": [po.organization_id for po in p.organizations],
        "location_codes":   [pl.location_code  for pl in p.locations],
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
def create_project(body: ProjectCreate, db: Session = Depends(get_db)):
    """Create a new project. Admin only."""
    _require_admin()

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
def update_project(project_id: str, body: ProjectUpdate, db: Session = Depends(get_db)):
    """Update project metadata. Admin only."""
    _require_admin()

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

@router.get("/projects/{project_id}/organizations")
def list_project_organizations(project_id: str, db: Session = Depends(get_db)):
    """List organizations linked to a project."""
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    rows = db.execute(
        select(ProjectOrganization).where(ProjectOrganization.project_id == project_id)
    ).scalars().all()
    return [{"project_id": r.project_id, "organization_id": r.organization_id} for r in rows]


@router.post("/projects/{project_id}/organizations/{organization_id}", status_code=201)
def add_project_organization(project_id: str, organization_id: str, db: Session = Depends(get_db)):
    """Link an organization to a project. Admin only."""
    _require_admin()

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
        raise HTTPException(status_code=409, detail="Organization already linked to this project")

    db.add(ProjectOrganization(project_id=project_id, organization_id=organization_id))
    db.commit()
    return {"project_id": project_id, "organization_id": organization_id}


@router.delete("/projects/{project_id}/organizations/{organization_id}", status_code=204)
def remove_project_organization(project_id: str, organization_id: str, db: Session = Depends(get_db)):
    """Unlink an organization from a project. Admin only."""
    _require_admin()

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
def add_project_location(project_id: str, location_code: str, db: Session = Depends(get_db)):
    """Link a location node to a project. Admin only."""
    _require_admin()

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
def remove_project_location(project_id: str, location_code: str, db: Session = Depends(get_db)):
    """Unlink a location from a project. Admin only."""
    _require_admin()

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
