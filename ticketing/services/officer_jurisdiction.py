"""Resolve officer scope rows against projects and tickets."""

from __future__ import annotations

from sqlalchemy import and_, false, or_, select, true
from sqlalchemy.orm import Session

from ticketing.constants.jurisdiction import (
    JURISDICTION_COUNTRY,
    JURISDICTION_GLOBAL,
    resolve_jurisdiction_mode,
)
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


def ticket_matches_scope(db: Session, scope: OfficerScope, ticket: Ticket) -> bool:
    """Python-side check (tests / admin tools). List API uses SQL builders below."""
    if is_global_scope(db, scope):
        return True
    if is_country_wide_scope(db, scope):
        codes = _project_short_codes_for_org(db, scope.organization_id)
        return bool(ticket.project_code and ticket.project_code in codes)
    parts = [ticket.organization_id == scope.organization_id]
    if scope.project_code and ticket.project_code != scope.project_code:
        return False
    if scope.location_code and ticket.location_code != scope.location_code:
        return False
    return parts[0]


def scope_ticket_filter(db: Session, scope: OfficerScope):
    """SQLAlchemy filter clause: tickets visible under this scope row."""
    if is_global_scope(db, scope):
        return true()
    if is_country_wide_scope(db, scope):
        codes = _project_short_codes_for_org(db, scope.organization_id)
        if not codes:
            return false()
        return Ticket.project_code.in_(codes)

    from ticketing.models.country import Location

    parts: list = [Ticket.organization_id == scope.organization_id]
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
    if scope.project_code:
        parts.append(Ticket.project_code == scope.project_code)
    return and_(*parts)
