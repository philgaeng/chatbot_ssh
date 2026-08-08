"""Which grievances belong to an organization — by membership, not by a stamp.

**Decided 2026-08-04** ([DECISION-organization-membership](../../docs/sprints/2026-07_org_chart_positions/DECISION-organization-membership.md)),
superseding the `routing_org_role` anchor:

> A grievance belongs to a **project**. Every organization named on that project sees it —
> donor, ministry, department, contractor alike. An organization named on a **single package** sees
> that package only. And because organizations form a tree ([doc 16 §3.1](../../docs/ticketing_system/16_org_chart_and_positions.md)),
> a parent sees everything its children see.

So the question "which grievances are the Department of Roads'?" is answered by *membership* —
`project_organizations` / `package_organizations`, widened down the org tree — and never by a
single `organization_id` written onto each ticket. That stamp could only ever name one body,
which is why it had to be authored, and why the answer was wrong for every other organization
on the project.

This mirrors what reports already do for **locations**: expand the tree, then match anything
inside it (`report_rows._location_codes_with_descendants`).
"""
from __future__ import annotations

from sqlalchemy import false, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from ticketing.models.package import PackageOrganization, ProjectPackage
from ticketing.models.project import Project, ProjectOrganization
from ticketing.models.ticket import Ticket


def org_reach_ids(db: Session, organization_id: str) -> set[str]:
    """``organization_id`` plus every organization beneath it (cycle-guarded)."""
    from ticketing.services.org_tree import descendant_org_ids

    return descendant_org_ids(db, organization_id, include_self=True)


def project_and_package_reach(
    db: Session, organization_id: str
) -> tuple[set[str], set[str]]:
    """(project_ids, package_ids) this organization's grievances come from.

    A **project-level** naming covers the whole project, packages included. A **package-level**
    naming covers that package only — naming a contractor on package 3 is a statement about package 3
    (Q1, 2026-08-04). The organization above it still sees everything, through the tree.
    """
    reach = org_reach_ids(db, organization_id)
    if not reach:
        return set(), set()

    project_ids = set(
        db.execute(
            select(ProjectOrganization.project_id).where(
                ProjectOrganization.organization_id.in_(reach)
            )
        ).scalars().all()
    )
    package_ids = set(
        db.execute(
            select(PackageOrganization.package_id).where(
                PackageOrganization.organization_id.in_(reach)
            )
        ).scalars().all()
    )
    # A package inside a project the organization already covers adds nothing.
    if package_ids and project_ids:
        redundant = set(
            db.execute(
                select(ProjectPackage.package_id).where(
                    ProjectPackage.package_id.in_(package_ids),
                    ProjectPackage.project_id.in_(project_ids),
                )
            ).scalars().all()
        )
        package_ids -= redundant
    return project_ids, package_ids


def ticket_filter_for_org(db: Session, organization_id: str) -> ColumnElement:
    """A WHERE clause selecting the grievances that belong to ``organization_id``.

    Returns a false clause when the organization is named nowhere — an organization with no
    projects has no grievances, which is not the same as "no filter".
    """
    project_ids, package_ids = project_and_package_reach(db, organization_id)
    clauses: list[ColumnElement] = []
    if project_ids:
        clauses.append(Ticket.project_id.in_(project_ids))
        # `project_code` is the deprecated ref chatbot-created tickets may still carry.
        clauses.append(
            Ticket.project_code.in_(
                select(Project.short_code).where(Project.project_id.in_(project_ids))
            )
        )
    if package_ids:
        clauses.append(Ticket.package_id.in_(package_ids))
    if not clauses:
        return false()
    return or_(*clauses)


def organization_ids_for_project(db: Session, project_id: str) -> list[str]:
    """Every organization named on a project — the report's "Organizations" column.

    Package-level names are included: they are part of the project's cast of organizations even
    though their *reach* is one package.
    """
    project_orgs = db.execute(
        select(ProjectOrganization.organization_id).where(
            ProjectOrganization.project_id == project_id
        )
    ).scalars().all()
    package_orgs = db.execute(
        select(PackageOrganization.organization_id)
        .join(ProjectPackage, ProjectPackage.package_id == PackageOrganization.package_id)
        .where(ProjectPackage.project_id == project_id)
    ).scalars().all()
    seen: list[str] = []
    for oid in [*project_orgs, *package_orgs]:
        if oid and oid not in seen:
            seen.append(oid)
    return seen
