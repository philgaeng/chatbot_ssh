"""
Resolve ticket routing organization from project / package actor configuration.

See docs/ticketing_system/13_projects_and_packages.md §6.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ticketing.models.package import PackageOrganization, ProjectPackage
from ticketing.models.project import Project, ProjectOrganization

logger = logging.getLogger(__name__)

DEFAULT_ROUTING_ORG_ROLE = "implementing_agency"


def routing_org_role_for_project(db: Session, project: Project) -> str:
    from ticketing.services.project_types import get_project_type

    pt = (
        get_project_type(db, project.project_type_key)
        if project.project_type_key
        else None
    )
    return (pt.routing_org_role if pt else None) or DEFAULT_ROUTING_ORG_ROLE


def _org_for_role_on_project(project: Project, org_role: str) -> Optional[str]:
    for po in project.organizations:
        if po.org_role == org_role:
            return po.organization_id
    return None


def _org_for_role_on_package(db: Session, package_id: str, org_role: str) -> Optional[str]:
    return db.execute(
        select(PackageOrganization.organization_id).where(
            PackageOrganization.package_id == package_id,
            PackageOrganization.org_role == org_role,
        ).limit(1)
    ).scalar_one_or_none()


def _load_project(
    db: Session,
    *,
    project_id: Optional[str] = None,
    project_code: Optional[str] = None,
) -> Optional[Project]:
    if project_id:
        return db.execute(
            select(Project)
            .options(selectinload(Project.organizations))
            .where(Project.project_id == project_id)
        ).scalar_one_or_none()
    code = (project_code or "").strip()
    if code:
        return db.execute(
            select(Project)
            .options(selectinload(Project.organizations))
            .where(Project.short_code == code)
        ).scalar_one_or_none()
    return None


def resolve_ticket_organization(
    db: Session,
    *,
    project_id: Optional[str] = None,
    project_code: Optional[str] = None,
    package_id: Optional[str] = None,
    location_code: Optional[str] = None,
) -> Optional[str]:
    """
    Commercial organization that owns ticket routing for intake / auto-assign.

    Priority:
      1. Package actor for routing role (overrides project-wide for that role)
      2. Project actor for routing role (from project type, default implementing_agency)

    location_code is accepted for future package-from-location resolution; unused today.
    """
    _ = location_code  # reserved

    project: Optional[Project] = None
    pkg_id = (package_id or "").strip() or None

    if pkg_id:
        pkg = db.get(ProjectPackage, pkg_id)
        if not pkg:
            logger.warning("resolve_ticket_organization: unknown package_id=%s", pkg_id)
        else:
            project = _load_project(db, project_id=pkg.project_id)
            if project:
                role = routing_org_role_for_project(db, project)
                pkg_org = _org_for_role_on_package(db, pkg_id, role)
                if pkg_org:
                    return pkg_org

    if not project:
        project = _load_project(
            db,
            project_id=(project_id or "").strip() or None,
            project_code=project_code,
        )

    if not project:
        return None

    role = routing_org_role_for_project(db, project)
    return _org_for_role_on_project(project, role)


def routing_org_id_for_loaded_project(db: Session, project: Project) -> Optional[str]:
    """Go-live helper when project.organizations is already eager-loaded."""
    role = routing_org_role_for_project(db, project)
    return _org_for_role_on_project(project, role)
