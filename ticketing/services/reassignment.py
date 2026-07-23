"""
Reassignment authority resolution (DESIGN-cast-model §3.4).

Reassignment is a **capability** (`can_reassign`), not a fifth cast tier, resolved through a
fallback chain that can **never dead-end**:

    1. Designated Dispatcher (staffed per package)   ← if set
    2. Supervisor slot (staffed per package)          ← default
    3. Actor self-serve                                ← if the per-step toggle is on
    4. project_admin                                   ← guaranteed backstop

This replaces the old heuristic in `request_reassignment` (which dead-ended with
"no supervisor available"). The Dispatcher is an officer holding the system
`reassign_dispatcher` scope (project-wide or per-package); project_admin is an admin-plane
holder over the ticket's project.

Note on project refs: `officer_scopes.project_id` is a UUID FK while `admin_scopes.project_id`
carries the project short_code, and a ticket may carry only `project_code`. Every lookup below
matches on **both** the UUID and the short_code so it works regardless of which is populated.
"""
from __future__ import annotations

from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ticketing.engine.workflow_engine import _find_supervisor_user_id, get_current_step
from ticketing.models.admin_scope import AdminScope
from ticketing.models.officer_scope import OfficerScope
from ticketing.models.project import Project
from ticketing.models.ticket import Ticket
from ticketing.models.workflow import WorkflowStep
from ticketing.services.officer_admin import officer_is_active

DISPATCHER_ROLE_KEY = "reassign_dispatcher"


@dataclass(frozen=True)
class ReassignmentAuthority:
    """The resolved reassignment authority. ``source`` ∈ dispatcher | supervisor | actor_self
    | project_admin | none."""

    user_id: str | None
    source: str


def _project_refs_from_ticket(db: Session, ticket: Ticket) -> list[str]:
    """Both the UUID and short_code for the ticket's project (whichever are resolvable)."""
    return _project_refs(db, ticket.project_id, ticket.project_code)


def _project_refs(db: Session, project_id: str | None, project_code: str | None) -> list[str]:
    refs: set[str] = set()
    if project_id:
        refs.add(project_id)
    if project_code:
        refs.add(project_code)
    # Fill in the missing ref so admin_scopes (short_code) and officer_scopes (UUID) both match.
    if project_id and not project_code:
        p = db.get(Project, project_id)
        if p:
            refs.add(p.short_code)
    elif project_code and not project_id:
        p = db.execute(sa.select(Project).where(Project.short_code == project_code)).scalar_one_or_none()
        if p:
            refs.add(p.project_id)
    return [r for r in refs if r]


def _first_active(db: Session, user_ids) -> str | None:
    for uid in user_ids:
        if officer_is_active(db, uid):
            return uid
    return None


def _dispatcher_holder(db: Session, project_refs: list[str], package_id: str | None) -> str | None:
    """An active Dispatcher for the project — a per-package holder wins over a project-wide one."""
    if not project_refs:
        return None
    base = (
        OfficerScope.role_key == DISPATCHER_ROLE_KEY,
        sa.or_(
            OfficerScope.project_id.in_(project_refs),
            OfficerScope.project_code.in_(project_refs),
        ),
    )
    for pkg_clause in (
        [OfficerScope.package_id == package_id] if package_id else [],
        [OfficerScope.package_id.is_(None)],
    ):
        rows = db.execute(sa.select(OfficerScope.user_id).where(*base, *pkg_clause)).scalars().all()
        uid = _first_active(db, rows)
        if uid:
            return uid
    return None


def _project_admin_holder(db: Session, project_refs: list[str]) -> str | None:
    """A project_admin over the project — the guaranteed backstop."""
    if not project_refs:
        return None
    rows = db.execute(
        sa.select(AdminScope.user_id).where(
            AdminScope.role_key == "project_admin",
            AdminScope.project_id.in_(project_refs),
        )
    ).scalars().all()
    return _first_active(db, rows)


def _pool_staffed(db: Session, project_refs: list[str], role_key: str | None) -> bool:
    """True if any active officer holds ``role_key`` scoped to this project."""
    if not project_refs or not role_key:
        return False
    rows = db.execute(
        sa.select(OfficerScope.user_id).where(
            OfficerScope.role_key == role_key,
            sa.or_(
                OfficerScope.project_id.in_(project_refs),
                OfficerScope.project_code.in_(project_refs),
            ),
        )
    ).scalars().all()
    return _first_active(db, rows) is not None


def dispatcher_for_ticket(db: Session, ticket: Ticket) -> str | None:
    """The active Dispatcher (if any) for a ticket's project/package — used by the assign gate."""
    return _dispatcher_holder(db, _project_refs_from_ticket(db, ticket), ticket.package_id)


def resolve_reassignment_authority(
    db: Session, ticket: Ticket, *, exclude_self: bool = False
) -> ReassignmentAuthority:
    """Resolve the reassignment authority for ``ticket`` via the §3.4 chain.

    ``exclude_self=True`` (the bounce-up case) skips the Actor self-serve rung — you cannot
    bounce a ticket to yourself; the toggle instead lets the assignee route it directly.
    """
    refs = _project_refs_from_ticket(db, ticket)
    step = get_current_step(ticket, db)

    disp = _dispatcher_holder(db, refs, ticket.package_id)
    if disp:
        return ReassignmentAuthority(disp, "dispatcher")

    sup = _find_supervisor_user_id(db, ticket)
    if sup:
        return ReassignmentAuthority(sup, "supervisor")

    if (
        not exclude_self
        and step is not None
        and getattr(step, "actor_can_reassign", False)
        and ticket.assigned_to_user_id
    ):
        return ReassignmentAuthority(ticket.assigned_to_user_id, "actor_self")

    pa = _project_admin_holder(db, refs)
    if pa:
        return ReassignmentAuthority(pa, "project_admin")

    return ReassignmentAuthority(None, "none")


# ── go-live: every step must resolve to a reassignment authority ─────────────

def step_has_reachable_reassigner(
    db: Session, *, project: Project, step: WorkflowStep
) -> bool:
    """True if the §3.4 chain resolves to someone for this (project, step) — the go-live
    invariant that kills the dead-end. project_admin is the guaranteed backstop, so this is
    False only when the project has no Dispatcher, no staffed Supervisor, no self-serve Actor
    pool, and no project_admin."""
    refs = _project_refs(db, project.project_id, project.short_code)
    if _dispatcher_holder(db, refs, None):
        return True
    if _pool_staffed(db, refs, step.supervisor_role):
        return True
    if getattr(step, "actor_can_reassign", False) and _pool_staffed(db, refs, step.assigned_role_key):
        return True
    return _project_admin_holder(db, refs) is not None
