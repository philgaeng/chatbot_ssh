# SPDX-License-Identifier: Apache-2.0

"""
Resolve ticket routing organization from project / package actor configuration.

See docs/ticketing_system/13_projects_and_packages.md §6.

Project lookup order (stable id first — short_code is admin-editable):
  1. project_id (FK / stable seed id)
  2. current short_code
  3. legacy chatbot alias (e.g. KL_ROAD → project_id)
"""
from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql.elements import ColumnElement

from ticketing.constants.projects import (
    CHATBOT_LEGACY_PROJECT_CODES,
    legacy_project_id_for_code,
)
from ticketing.models.package import PackageOrganization, ProjectPackage
from ticketing.models.project import Project, ProjectOrganization

if TYPE_CHECKING:
    from ticketing.models.ticket import Ticket

logger = logging.getLogger(__name__)

def _required_role_order(db: Session, project: Project) -> list[str]:
    """The type's **required** organization roles, in the order the author listed them.

    Required, not merely listed: the back-fill migration writes catalog keys in alphabetical
    order, so on a migrated type "first listed" is `donor` — an accident of sorting, not a
    statement about the project. `required` is the author saying *every project of this kind
    must have this one*, which is the same thing the creation flow fills.
    """
    from ticketing.services.project_types import get_project_type

    if not project.project_type_key:
        return []
    pt = get_project_type(db, project.project_type_key)
    if not pt:
        return []
    return [
        str(e.get("key"))
        for e in (pt.actor_roles or [])
        if e.get("key") and e.get("required")
    ]


def _primary_org_for_project(db: Session, project: Project) -> Optional[str]:
    """The project's **lead** organization: the first required role the type names.

    Descriptive only. Until 2026-08-04 this was the author-designated *anchor*
    (`routing_org_role`) and it decided which organization a grievance was reported under —
    which meant one organization owned the grievance and every other one on the project owned
    nothing. **That idea is gone** (DECISION-organization-membership): reporting is membership,
    computed in `services/org_reach.py`, and reads none of this.

    What remains needs a value only because `tickets.organization_id` is NOT NULL and rides
    along in a few payloads. Order: first required role → the legacy accountable-organization
    field → any organization named on the project.
    """
    by_role = {po.org_role: po.organization_id for po in project.organizations if po.org_role}
    for role in _required_role_order(db, project):
        if by_role.get(role):
            return by_role[role]
    if project.implementing_agency_org_id:
        return project.implementing_agency_org_id
    for po in project.organizations:
        if po.organization_id:
            return po.organization_id
    return None


def _primary_org_for_package(db: Session, package_id: str) -> Optional[str]:
    return db.execute(
        select(PackageOrganization.organization_id)
        .where(PackageOrganization.package_id == package_id)
        .limit(1)
    ).scalar_one_or_none()


def known_project_code_refs(project: Project) -> set[str]:
    """Denormalized project_code strings that may appear on tickets / officer scopes."""
    refs: set[str] = set()
    if project.short_code and project.short_code.strip():
        refs.add(project.short_code.strip())
    for alias, pid in CHATBOT_LEGACY_PROJECT_CODES.items():
        if pid == project.project_id:
            refs.add(alias)
    return refs


def project_ref_match_clause(
    *,
    project_id_col: ColumnElement,
    project_code_col: ColumnElement,
    project: Project,
    extra_ref: str | None = None,
) -> ColumnElement:
    """SQL OR matching a project by stable id or any known denormalized code."""
    refs = known_project_code_refs(project)
    if extra_ref and extra_ref.strip():
        refs.add(extra_ref.strip())
    clauses: list[ColumnElement] = [project_id_col == project.project_id]
    if refs:
        clauses.append(project_code_col.in_(list(refs)))
    return or_(*clauses)


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
    if not code:
        return None
    # Stable id may be passed where callers still label the field project_code.
    by_id = db.execute(
        select(Project)
        .options(selectinload(Project.organizations))
        .where(Project.project_id == code)
    ).scalar_one_or_none()
    if by_id:
        return by_id
    project = db.execute(
        select(Project)
        .options(selectinload(Project.organizations))
        .where(Project.short_code == code)
    ).scalar_one_or_none()
    if project:
        return project
    legacy_id = legacy_project_id_for_code(code)
    if legacy_id:
        return _load_project(db, project_id=legacy_id)
    return None


def load_project_ref(db: Session, ref: Optional[str]) -> Optional[Project]:
    """Resolve project: project_id → short_code → legacy alias."""
    return _load_project(db, project_code=ref)


def load_project_by_code(db: Session, project_code: Optional[str]) -> Optional[Project]:
    """Backward-compatible alias for load_project_ref."""
    return load_project_ref(db, project_code)


def load_project_for_ticket(db: Session, ticket: "Ticket") -> Optional[Project]:
    """Prefer ticket.project_id; fall back to denormalized project_code / legacy alias."""
    if ticket.project_id:
        project = db.execute(
            select(Project)
            .options(selectinload(Project.organizations))
            .where(Project.project_id == ticket.project_id)
        ).scalar_one_or_none()
        if project:
            return project
    if ticket.project_code:
        return load_project_ref(db, ticket.project_code)
    return None


def officer_scope_project_code_match(
    db: Session,
    project_ref: Optional[str],
) -> ColumnElement:
    """Match OfficerScope.project_code only (legacy rows without project_id)."""
    from ticketing.models.officer_scope import OfficerScope

    if project_ref is None:
        return OfficerScope.project_code.is_(None)
    project = load_project_ref(db, project_ref)
    if project:
        refs = known_project_code_refs(project)
        refs.add(project_ref.strip())
        return OfficerScope.project_code.in_(list(refs))
    return OfficerScope.project_code == project_ref


def officer_scope_project_match(
    db: Session,
    project_ref: Optional[str],
) -> ColumnElement:
    """
    Match OfficerScope rows for a project ref (or org-wide when ref is None).

    Uses project_id when resolved; also matches legacy/denormalized project_code values.
    """
    from ticketing.models.officer_scope import OfficerScope

    if project_ref is None:
        return and_(
            OfficerScope.project_code.is_(None),
            OfficerScope.project_id.is_(None),
        )
    project = load_project_ref(db, project_ref)
    if project:
        return project_ref_match_clause(
            project_id_col=OfficerScope.project_id,
            project_code_col=OfficerScope.project_code,
            project=project,
            extra_ref=project_ref,
        )
    return OfficerScope.project_code == project_ref


def ticket_project_match_clause(db: Session, project_ref: str) -> ColumnElement:
    """Match Ticket rows for a project filter (id + known denormalized codes)."""
    from ticketing.models.ticket import Ticket

    project = load_project_ref(db, project_ref)
    if project:
        return project_ref_match_clause(
            project_id_col=Ticket.project_id,
            project_code_col=Ticket.project_code,
            project=project,
            extra_ref=project_ref,
        )
    return Ticket.project_code == project_ref


def resolve_ticket_organization(
    db: Session,
    *,
    project_id: Optional[str] = None,
    project_code: Optional[str] = None,
    package_id: Optional[str] = None,
    location_code: Optional[str] = None,
) -> Optional[str]:
    """
    The organization stamped on a new ticket (`tickets.organization_id`).

    **Descriptive since 2026-08-04** (DECISION-organization-membership). It used to be *the*
    organization a grievance was reported under, chosen by the project type's
    ``routing_org_role``. Reporting is now **membership** — every organization named on the
    project sees the grievance, a lot-level naming reaches that lot, and a parent organization
    sees everything its children see (`services/org_reach.py`). Nothing reads this field to
    decide who sees what.

    Order: the lot's first organization (a lot is more specific), else the project's
    first-named organization, else the legacy ``implementing_agency_org_id``.

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
            pkg_org = _primary_org_for_package(db, pkg_id)
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

    return _primary_org_for_project(db, project)


def routing_org_id_for_loaded_project(db: Session, project: Project) -> Optional[str]:
    """Helper for callers that already eager-loaded ``project.organizations``."""
    return _primary_org_for_project(db, project)
