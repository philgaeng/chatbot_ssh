"""
In-process workflow engine for GRM Ticketing.

Responsibilities:
  - Step navigation (first, next, current)
  - SLA deadline computation
  - SLA breach detection
  - Step display helpers for UI
  - Officer auto-assignment (least-loaded within scope)

This module is pure business logic — no side effects, no DB writes.
All mutations happen in escalation.py (which calls these helpers).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ticketing.models.ticket import Ticket
from ticketing.models.workflow import WorkflowAssignment, WorkflowDefinition, WorkflowStep


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Step navigation ────────────────────────────────────────────────────────────

def get_current_step(ticket: Ticket, db: Session) -> Optional[WorkflowStep]:
    """Return the WorkflowStep for the ticket's current_step_id, or None."""
    if not ticket.current_step_id:
        return None
    return db.get(WorkflowStep, ticket.current_step_id)


def get_next_step(ticket: Ticket, db: Session) -> Optional[WorkflowStep]:
    """
    Return the next WorkflowStep in the workflow, or None if ticket is at the last step.
    Ordered by step_order ascending.
    """
    current = get_current_step(ticket, db)
    current_order = current.step_order if current else 0
    return db.execute(
        select(WorkflowStep)
        .where(
            WorkflowStep.workflow_id == ticket.current_workflow_id,
            WorkflowStep.step_order > current_order,
        )
        .order_by(WorkflowStep.step_order)
        .limit(1)
    ).scalar_one_or_none()


def get_first_step(workflow_id: str, db: Session) -> Optional[WorkflowStep]:
    """Return step with the lowest step_order for a workflow."""
    return db.execute(
        select(WorkflowStep)
        .where(WorkflowStep.workflow_id == workflow_id)
        .order_by(WorkflowStep.step_order)
        .limit(1)
    ).scalar_one_or_none()


def is_final_step(ticket: Ticket, db: Session) -> bool:
    """True if the ticket is on the last step of its workflow (no next step)."""
    return get_next_step(ticket, db) is None


# ── SLA computation ────────────────────────────────────────────────────────────

def compute_sla_deadline(ticket: Ticket, step: Optional[WorkflowStep]) -> Optional[datetime]:
    """
    Compute the absolute UTC datetime by which this step must be resolved.

    Returns None if:
      - The step has no resolution_time_days (e.g. Level 4 legal)
      - step_started_at is not set yet (ticket not yet acknowledged)
    """
    if step is None or step.resolution_time_days is None:
        return None
    clock_start = ticket.step_started_at or ticket.created_at
    if clock_start is None:
        return None
    return clock_start + timedelta(days=step.resolution_time_days)


def sla_status(ticket: Ticket, step: Optional[WorkflowStep]) -> dict:
    """
    Return a dict with SLA status for UI display:
      {
        "deadline": datetime | None,
        "breached": bool,
        "remaining_hours": float | None,  # negative = overdue
        "urgency": "overdue" | "critical" | "warning" | "ok" | "none"
      }
    urgency levels:
      overdue   → already breached (< 0h)
      critical  → < 24h remaining
      warning   → < 72h remaining
      ok        → > 72h remaining
      none      → no SLA defined
    """
    deadline = compute_sla_deadline(ticket, step)
    if deadline is None:
        return {"deadline": None, "breached": False, "remaining_hours": None, "urgency": "none"}

    now = _now()
    # Ensure deadline is timezone-aware
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)

    remaining = (deadline - now).total_seconds() / 3600
    breached = remaining <= 0

    if breached:
        urgency = "overdue"
    elif remaining < 24:
        urgency = "critical"
    elif remaining < 72:
        urgency = "warning"
    else:
        urgency = "ok"

    return {
        "deadline": deadline,
        "breached": breached,
        "remaining_hours": round(remaining, 1),
        "urgency": urgency,
    }


def is_sla_breached(ticket: Ticket, step: Optional[WorkflowStep]) -> bool:
    """Quick check: has the SLA deadline passed?"""
    deadline = compute_sla_deadline(ticket, step)
    if deadline is None:
        return False
    now = _now()
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    return now > deadline


# ── Workflow assignment lookup ─────────────────────────────────────────────────

def resolve_workflow(
    organization_id: str,
    location_code: Optional[str],
    project_code: Optional[str],
    is_seah: bool,
    priority: str,
    db: Session,
) -> Optional[WorkflowDefinition]:
    """
    Find the best-matching WorkflowDefinition for the given ticket parameters.

    For SEAH tickets, priority is treated as 'SEAH' for lookup purposes.
    Falls back through: exact match → no location → no project → no priority.
    """
    lookup_priority = "SEAH" if is_seah else priority

    for loc in ([location_code, None] if location_code else [None]):
        for proj in ([project_code, None] if project_code else [None]):
            for pri in ([lookup_priority, None]):
                assignment = db.execute(
                    select(WorkflowAssignment).where(
                        WorkflowAssignment.organization_id == organization_id,
                        WorkflowAssignment.location_code == loc,
                        WorkflowAssignment.project_code == proj,
                        WorkflowAssignment.priority == pri,
                    )
                ).scalar_one_or_none()
                if assignment:
                    return db.get(WorkflowDefinition, assignment.workflow_id)
    return None


# ── GRC helpers ───────────────────────────────────────────────────────────────

def get_grc_member_user_ids(
    organization_id: str,
    location_code: Optional[str],
    db: Session,
) -> list[str]:
    """
    Return user_ids of all officers with grc_member or grc_chair role
    for the given org + location. Used to notify all GRC members on convening.
    """
    from sqlalchemy import select
    from ticketing.models.user import Role, UserRole

    grc_keys = {"grc_chair", "grc_member"}

    # Get role IDs for GRC keys
    roles = db.execute(
        select(Role).where(Role.role_key.in_(grc_keys))
    ).scalars().all()
    role_ids = [r.role_id for r in roles]
    if not role_ids:
        return []

    q = (
        select(UserRole.user_id)
        .where(
            UserRole.role_id.in_(role_ids),
            UserRole.organization_id == organization_id,
        )
        .distinct()
    )
    if location_code:
        q = q.where(
            (UserRole.location_code == location_code) | (UserRole.location_code.is_(None))
        )

    rows = db.execute(q).all()
    return [row[0] for row in rows]


# ── Location ancestor helpers ─────────────────────────────────────────────────

def _location_and_ancestors(location_code: str, db: Session) -> list[str]:
    """
    Return [location_code] + all ancestor location_codes (parent, grandparent, …).
    Uses a recursive CTE on ticketing.locations.
    Returns an empty list if location_code is not in the DB.
    """
    import sqlalchemy as sa
    cte = sa.text("""
        WITH RECURSIVE ancestors AS (
            SELECT location_code, parent_location_code
            FROM ticketing.locations
            WHERE location_code = :lc
            UNION ALL
            SELECT l.location_code, l.parent_location_code
            FROM ticketing.locations l
            JOIN ancestors a ON l.location_code = a.parent_location_code
        )
        SELECT location_code FROM ancestors
    """)
    rows = db.execute(cte, {"lc": location_code}).scalars().all()
    return list(rows)


def _scope_candidates(
    role_key: str,
    organization_id: str,
    location_code: Optional[str],
    project_code: Optional[str],
    db: Session,
) -> list[str]:
    """
    Return all user_ids whose scopes cover the given (role, org, location, project).

    Matching rules (union of all three):
      A. Exact / wildcard location match (non-package scopes only):
         scope.package_id    IS NULL  (package-scoped officers handled by C)
         scope.location_code == location_code (or IS NULL for "all locations")
         scope.project_code  == project_code  (or IS NULL for "all projects")

      B. includes_children cascade (non-package scopes only):
         scope.package_id    IS NULL
         scope.includes_children IS TRUE
         scope.location_code IS an ancestor of location_code
         scope.project_code  == project_code  (or IS NULL)

      C. Package-scoped officers:
         Find packages whose PackageLocation rows cover location_code (or any ancestor).
         Match officers whose scope.package_id is one of those packages.

    Both A, B, and C require role_key + organization_id to match exactly.
    """
    from ticketing.models.officer_scope import OfficerScope
    from ticketing.models.package import PackageLocation

    seen: set[str] = set()
    result: list[str] = []

    def _add(uids: list[str]) -> None:
        for uid in uids:
            if uid not in seen:
                seen.add(uid)
                result.append(uid)

    # ── A. Exact / wildcard match (non-package scopes only) ───────────────────
    for loc in ([location_code, None] if location_code else [None]):
        for proj in ([project_code, None] if project_code else [None]):
            rows = db.execute(
                select(OfficerScope.user_id).where(
                    OfficerScope.role_key        == role_key,
                    OfficerScope.organization_id == organization_id,
                    OfficerScope.location_code   == loc,
                    OfficerScope.project_code    == proj,
                    OfficerScope.package_id.is_(None),   # exclude package-scoped officers
                )
            ).scalars().all()
            _add(rows)

    # ── B. includes_children: scope covers an ancestor (non-package scopes only)
    if location_code:
        ancestors = _location_and_ancestors(location_code, db)
        # Exclude the exact location itself (already covered by A)
        ancestor_only = [a for a in ancestors if a != location_code]
        if ancestor_only:
            for proj in ([project_code, None] if project_code else [None]):
                rows = db.execute(
                    select(OfficerScope.user_id).where(
                        OfficerScope.role_key          == role_key,
                        OfficerScope.organization_id   == organization_id,
                        OfficerScope.location_code.in_(ancestor_only),
                        OfficerScope.includes_children.is_(True),
                        OfficerScope.project_code      == proj,
                        OfficerScope.package_id.is_(None),   # exclude package-scoped officers
                    )
                ).scalars().all()
                _add(rows)

    # ── C. Package-scoped officers: match via PackageLocation coverage ─────────
    # An officer scoped to package P covers any ticket whose location is in P's
    # PackageLocation rows (or any ancestor of the ticket's location).
    if location_code:
        all_locs = _location_and_ancestors(location_code, db)
        covering_pkg_ids = db.execute(
            select(PackageLocation.package_id).where(
                PackageLocation.location_code.in_(all_locs)
            )
        ).scalars().all()
        if covering_pkg_ids:
            rows = db.execute(
                select(OfficerScope.user_id).where(
                    OfficerScope.role_key        == role_key,
                    OfficerScope.organization_id == organization_id,
                    OfficerScope.package_id.in_(covering_pkg_ids),
                )
            ).scalars().all()
            _add(rows)

    return result


# ── Officer auto-assignment ───────────────────────────────────────────────────

def auto_assign_officer(
    role_key: str,
    organization_id: str,
    location_code: Optional[str],
    project_code: Optional[str],
    db: Session,
) -> Optional[str]:
    """
    Find the best officer to assign a ticket to.

    Candidate scope rules (see _scope_candidates):
      - Exact match on (role, org, location, project)
      - Wildcard: location=None covers all, project=None covers all
      - includes_children: officer scoped to an ancestor location covers descendants

    Among candidates, picks the least-loaded (fewest non-resolved assigned tickets).
    Returns user_id or None if no officer is configured for this scope.
    """
    from sqlalchemy import func as sqlfunc

    candidates = _scope_candidates(role_key, organization_id, location_code, project_code, db)
    if not candidates:
        return None

    # Count active tickets per candidate
    active_counts: dict[str, int] = dict(
        db.execute(
            select(Ticket.assigned_to_user_id, sqlfunc.count(Ticket.ticket_id))
            .where(
                Ticket.assigned_to_user_id.in_(candidates),
                Ticket.status_code.notin_(["RESOLVED", "CLOSED"]),
                Ticket.is_deleted.is_(False),
            )
            .group_by(Ticket.assigned_to_user_id)
        ).all()
    )

    return min(candidates, key=lambda uid: active_counts.get(uid, 0))


def get_teammates(
    role_key: str,
    organization_id: str,
    location_code: Optional[str],
    project_code: Optional[str],
    exclude_user_id: Optional[str],
    db: Session,
) -> list[str]:
    """
    Return all officers with the same role + scope as the given ticket.
    Used to populate the reassign dropdown. Excludes the currently assigned officer.
    Respects includes_children cascade same as auto_assign_officer.
    """
    candidates = _scope_candidates(role_key, organization_id, location_code, project_code, db)
    return [uid for uid in candidates if uid != exclude_user_id]
