"""Resolve officer scope rows against projects and tickets."""

from __future__ import annotations

from sqlalchemy import and_, false, or_, select, true
from sqlalchemy.orm import Session

from ticketing.constants.jurisdiction import (
    JURISDICTION_COUNTRY,
    JURISDICTION_GLOBAL,
    resolve_jurisdiction_mode,
)
from ticketing.models.country import Location
from ticketing.models.officer_scope import OfficerScope
from ticketing.models.project import Project, ProjectOrganization
from ticketing.models.ticket import Ticket
from ticketing.models.user import Role


def _project_short_codes_for_org(db: Session, organization_id: str) -> list[str]:
    rows = db.execute(
        select(Project.short_code)
        .join(
            ProjectOrganization,
            ProjectOrganization.project_id == Project.project_id,
        )
        .where(ProjectOrganization.organization_id == organization_id)
        .distinct()
    ).scalars().all()
    return [c for c in rows if c]


def jurisdiction_mode_for_scope(db: Session, scope: OfficerScope) -> str:
    role = db.execute(
        select(Role).where(Role.role_key == scope.role_key)
    ).scalar_one_or_none()
    stored = role.jurisdiction_mode if role else None
    return resolve_jurisdiction_mode(scope.role_key, stored)


def is_country_wide_scope(db: Session, scope: OfficerScope) -> bool:
    """Org-only scope for a country-mode role (covers all linked projects)."""
    if scope.location_code or scope.package_id:
        return False
    if scope.project_code or scope.project_id:
        return False
    return jurisdiction_mode_for_scope(db, scope) == JURISDICTION_COUNTRY


def is_global_scope(db: Session, scope: OfficerScope) -> bool:
    if scope.location_code or scope.package_id or scope.project_code or scope.project_id:
        return False
    return jurisdiction_mode_for_scope(db, scope) == JURISDICTION_GLOBAL


def scope_requires_field_jurisdiction(db: Session, role_key: str) -> bool:
    role = db.execute(select(Role).where(Role.role_key == role_key)).scalar_one_or_none()
    mode = resolve_jurisdiction_mode(role_key, role.jurisdiction_mode if role else None)
    return mode == "field"


def _location_matches(scope_loc: str | None, ticket_loc: str | None, db: Session) -> bool:
    if not scope_loc:
        return True
    if not ticket_loc:
        return False
    if scope_loc == ticket_loc:
        return True
    child_locs = db.execute(
        select(Location.location_code).where(Location.parent_location_code == scope_loc)
    ).scalars().all()
    return ticket_loc in child_locs


def ticket_matches_scope(db: Session, scope: OfficerScope, ticket: Ticket) -> bool:
    """Python-side check (tests / admin tools). List API uses SQL builders below."""
    if is_global_scope(db, scope):
        return True
    if is_country_wide_scope(db, scope):
        codes = _project_short_codes_for_org(db, scope.organization_id)
        return bool(ticket.project_code and ticket.project_code in codes)
    if scope.package_id and ticket.package_id != scope.package_id:
        return False
    if scope.project_code and ticket.project_code != scope.project_code:
        return False
    if scope.project_id and ticket.project_id and ticket.project_id != scope.project_id:
        return False
    return _location_matches(scope.location_code, ticket.location_code, db)


def scope_ticket_filter(db: Session, scope: OfficerScope):
    """SQLAlchemy filter clause: tickets visible under this scope row."""
    if is_global_scope(db, scope):
        return true()
    if is_country_wide_scope(db, scope):
        codes = _project_short_codes_for_org(db, scope.organization_id)
        if not codes:
            return false()
        return Ticket.project_code.in_(codes)

    parts: list = []

    if scope.package_id:
        parts.append(Ticket.package_id == scope.package_id)
    elif scope.project_id:
        parts.append(Ticket.project_id == scope.project_id)
    elif scope.project_code:
        parts.append(Ticket.project_code == scope.project_code)

    if scope.location_code:
        child_locs = select(Location.location_code).where(
            Location.parent_location_code == scope.location_code
        )
        parts.append(
            or_(
                Ticket.location_code == scope.location_code,
                Ticket.location_code.in_(child_locs),
            )
        )

    if not parts:
        return false()

    return and_(*parts)
