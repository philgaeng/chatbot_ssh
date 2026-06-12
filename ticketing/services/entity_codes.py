"""Helpers for project/package code assignment and project short_code renames."""
from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ticketing.constants.entity_codes import validate_entity_code
from ticketing.models.officer_scope import OfficerScope
from ticketing.models.package import ProjectPackage
from ticketing.models.project import Project
from ticketing.models.ticket import Ticket


def next_package_code(db: Session, project_id: str) -> str:
    """Suggest the next zero-padded numeric code (01, 02, …) for a project."""
    codes = db.execute(
        select(ProjectPackage.package_code).where(ProjectPackage.project_id == project_id)
    ).scalars().all()
    numeric: list[int] = []
    for code in codes:
        if code.isdigit():
            numeric.append(int(code))
    n = max(numeric, default=0) + 1
    if n < 100:
        return f"{n:02d}"
    return str(n)[:8]


def rename_project_short_code(db: Session, project: Project, new_code: str) -> None:
    """Apply short_code change and cascade to denormalized project_code fields."""
    normalized = validate_entity_code(new_code, field="Project code")
    old_code = project.short_code
    if normalized == old_code:
        return

    conflict = db.execute(
        select(Project.project_id).where(
            Project.short_code == normalized,
            Project.project_id != project.project_id,
        )
    ).scalar_one_or_none()
    if conflict:
        raise ValueError(f"Project code '{normalized}' is already in use.")

    project.short_code = normalized

    db.execute(
        update(OfficerScope)
        .where(OfficerScope.project_id == project.project_id)
        .values(project_code=normalized)
    )
    db.execute(
        update(OfficerScope)
        .where(
            OfficerScope.project_code == old_code,
            OfficerScope.project_id.is_(None),
        )
        .values(project_code=normalized)
    )
    db.execute(
        update(Ticket)
        .where(Ticket.project_id == project.project_id)
        .values(project_code=normalized)
    )
    db.execute(
        update(Ticket)
        .where(
            Ticket.project_code == old_code,
            Ticket.project_id.is_(None),
        )
        .values(project_code=normalized)
    )
