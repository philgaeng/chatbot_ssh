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
from typing import Any, Literal, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ticketing.constants.assignment import COUNTRY_L1_FALLBACK_ROLE
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
    *,
    grievance_categories: Optional[Any] = None,
    intake_route: Optional[str] = None,
    intake_fast_path: Optional[str] = None,  # deprecated — story_main intake_route only
) -> Optional[WorkflowDefinition]:
    """
    Resolve the workflow for a new ticket.

    1. Project workflow bindings (classifications + intake routes + default).
    2. Legacy projects.standard_workflow_id / seah_workflow_id columns.
    3. Legacy ticketing.workflow_assignments (org / location / project / priority).
    """
    from ticketing.services.project_routing import load_project_by_code
    from ticketing.services.workflow_routing import resolve_project_workflow

    if project_code:
        project = load_project_by_code(db, project_code)
        if project:
            wf = resolve_project_workflow(
                db,
                project.project_id,
                grievance_categories=grievance_categories,
                intake_route=intake_route,
                legacy_is_seah=is_seah,
            )
            if wf:
                return wf
            # Legacy fallback must respect the track: a SEAH grievance resolves to the SEAH
            # workflow first, a standard one to the standard workflow first. (Was is_seah-blind
            # — always returned standard first — latent while project_workflows had bindings.)
            legacy_order = (
                (project.seah_workflow_id, project.standard_workflow_id)
                if is_seah
                else (project.standard_workflow_id, project.seah_workflow_id)
            )
            for wf_id in legacy_order:
                if wf_id:
                    legacy = db.get(WorkflowDefinition, wf_id)
                    if legacy:
                        return legacy

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

GRC_ROLE_KEYS = ("grc_chair", "grc_member")


def get_grc_members_for_ticket(db: Session, ticket) -> list[str]:
    """The GRC members to notify when a hearing is convened on ``ticket``.

    **Changed 2026-08-04** (DECISION-organization-membership). This used to select officers by
    ``UserRole.organization_id == ticket.organization_id`` — the single organization stamped on
    the grievance. That stamp is gone as a concept: a grievance belongs to every organization
    named on its project, so "the committee of *the* organization" no longer identifies anyone.

    A GRC is convened **for a project**, so its members are resolved the way every other
    assignment on this system is: the GRC roles, scoped to the ticket's project / location /
    lot. Same predicate as `auto_assign_officer`, so a committee that can be assigned work can
    also be summoned to hear it — no second, divergent notion of "who is on the GRC".

    SEAH suppression is the caller's job (an ordinary GRC member must not learn a sensitive
    case exists) — see `escalation.convene_grc`.
    """
    seen: list[str] = []
    for role_key in GRC_ROLE_KEYS:
        for uid in _scope_candidates(
            role_key,
            ticket.organization_id,  # ignored by the predicate; kept for call compatibility
            ticket.location_code,
            ticket.project_code,
            db,
            ticket.package_id,
        ):
            if uid not in seen:
                seen.append(uid)
    return seen


def get_grc_member_user_ids(
    organization_id: str,
    location_code: Optional[str],
    db: Session,
) -> list[str]:
    """Legacy org+location GRC lookup. Superseded by :func:`get_grc_members_for_ticket`;
    kept only for callers that have no ticket in hand."""
    from sqlalchemy import select
    from ticketing.models.user import Role, UserRole

    # Get role IDs for GRC keys
    roles = db.execute(
        select(Role).where(Role.role_key.in_(set(GRC_ROLE_KEYS)))
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


def _province_code_for_location(location_code: str, db: Session) -> Optional[str]:
    """Return the level-1 (province) ancestor for *location_code*, or None."""
    from ticketing.models.country import Location

    for code in _location_and_ancestors(location_code, db):
        loc = db.get(Location, code)
        if loc is not None and loc.level_number == 1:
            return code
    return None


def _location_codes_in_province(province_code: str, db: Session) -> list[str]:
    """All location_code values in the province subtree (province + districts + munis, …)."""
    import sqlalchemy as sa

    rows = db.execute(
        sa.text("""
            WITH RECURSIVE subtree AS (
                SELECT location_code
                FROM ticketing.locations
                WHERE location_code = :prov
                UNION ALL
                SELECT l.location_code
                FROM ticketing.locations l
                JOIN subtree s ON l.parent_location_code = s.location_code
            )
            SELECT location_code FROM subtree
        """),
        {"prov": province_code},
    ).scalars().all()
    return list(rows)


def _optional_project_code_match(db: Session, project_ref: Optional[str]):
    """SQL match for optional project on officer scopes (stable id + legacy codes)."""
    from ticketing.services.project_routing import officer_scope_project_match

    return officer_scope_project_match(db, project_ref)


def _add_province_level_fallback(
    result: list[str],
    seen: set[str],
    *,
    role_key: str,
    organization_id: str,
    location_code: str,
    project_code: Optional[str],
    db: Session,
) -> None:
    """
    When no officer matched the ticket's exact area, widen to the whole province (level 1).

    Example: ticket in Jhapa (P1_JHA / P1_JHA_BIR) with no Jhapa-scoped L1 → any L1 scoped
    anywhere under Koshi (P1), e.g. Morang (P1_MOR), is eligible (least-loaded wins).
    """
    from ticketing.models.officer_scope import OfficerScope

    def _add(uids: list[str]) -> None:
        for uid in uids:
            if uid not in seen:
                seen.add(uid)
                result.append(uid)

    province = _province_code_for_location(location_code, db)
    if not province:
        return

    pool = _location_codes_in_province(province, db)
    if not pool:
        return

    base = (
        OfficerScope.role_key == role_key,
        OfficerScope.package_id.is_(None),
    )
    for proj in ([project_code, None] if project_code else [None]):
        rows = db.execute(
            select(OfficerScope.user_id).where(
                *base,
                OfficerScope.location_code.in_(pool),
                _optional_project_code_match(db, proj),
            )
        ).scalars().all()
        _add(rows)


AssignmentTier = Literal["field", "country_fallback"]


def _scope_country_fallback_candidates(
    role_key: str,
    organization_id: str,
    project_code: Optional[str],
    db: Session,
) -> list[str]:
    """
    Country-wide pool for country_l1_fallback only.

    Officers must be scoped with location_code=NULL (org + optional project).
    Never used for field roles — see assignment_tier='field'.
    """
    from ticketing.models.officer_scope import OfficerScope
    from ticketing.services.officer_admin import officer_is_active
    from ticketing.services.project_routing import (
        load_project_ref,
        officer_scope_project_code_match,
    )

    seen: set[str] = set()
    result: list[str] = []

    def _add(uids: list[str]) -> None:
        for uid in uids:
            if uid not in seen:
                seen.add(uid)
                if not officer_is_active(db, uid):  # R3: deactivated officers out of the pool
                    continue
                result.append(uid)

    base = (
        OfficerScope.role_key == role_key,
        OfficerScope.location_code.is_(None),
        OfficerScope.package_id.is_(None),
    )
    for proj in ([project_code, None] if project_code else [None]):
        rows = db.execute(
            select(OfficerScope.user_id).where(
                *base,
                officer_scope_project_code_match(db, proj),
                OfficerScope.project_id.is_(None),
            )
        ).scalars().all()
        _add(rows)

    if project_code:
        proj = load_project_ref(db, project_code)
        if proj:
            rows = db.execute(
                select(OfficerScope.user_id).where(
                    OfficerScope.role_key == role_key,
                    OfficerScope.project_id == proj.project_id,
                    OfficerScope.location_code.is_(None),
                    OfficerScope.package_id.is_(None),
                )
            ).scalars().all()
            _add(rows)

    return result


def _scope_candidates(
    role_key: str,
    organization_id: str,
    location_code: Optional[str],
    project_code: Optional[str],
    db: Session,
    ticket_package_id: Optional[str] = None,
    *,
    assignment_tier: AssignmentTier = "field",
) -> list[str]:
    """
    Return user_ids whose scopes cover (role, location, project, package).

    organization_id is accepted for call-site compatibility but is not used to
    filter candidates — assignment is by workflow role + jurisdiction only.

    assignment_tier='field' (default):
      District/municipality → ancestor includes_children → package paths →
      province widening. Does NOT match location_code=NULL field scopes (no
      org-wide competition). country_l1_fallback never matches here.

    assignment_tier='country_fallback':
      Only country_l1_fallback with country-wide scopes — last resort after
      field tier finds nobody.
    """
    if assignment_tier == "country_fallback":
        if role_key != COUNTRY_L1_FALLBACK_ROLE:
            return []
        return _scope_country_fallback_candidates(
            role_key, organization_id, project_code, db
        )

    if role_key == COUNTRY_L1_FALLBACK_ROLE:
        return []

    from ticketing.models.officer_scope import OfficerScope
    from ticketing.models.package import PackageLocation, ProjectPackage
    from ticketing.models.project import Project
    from ticketing.services.officer_admin import officer_is_active

    seen: set[str] = set()
    result: list[str] = []

    def _add(uids: list[str]) -> None:
        for uid in uids:
            if uid not in seen:
                seen.add(uid)
                # R3 (BUILD-REVIEW M2): a soft-deactivated officer is out of the assignment
                # pool — the system assignment path never passes through enrich_user, so it
                # must exclude them here or tickets auto-route to someone who can't log in.
                if not officer_is_active(db, uid):
                    continue
                result.append(uid)

    base = (OfficerScope.role_key == role_key,)

    # ── D. Ticket has explicit package_id (spec §4.4) ─────────────────────────
    if ticket_package_id:
        pkg = db.get(ProjectPackage, ticket_package_id)
        rows = db.execute(
            select(OfficerScope.user_id).where(
                *base,
                OfficerScope.package_id == ticket_package_id,
            )
        ).scalars().all()
        _add(rows)
        if pkg:
            rows = db.execute(
                select(OfficerScope.user_id).where(
                    *base,
                    OfficerScope.package_id.is_(None),
                    OfficerScope.project_id == pkg.project_id,
                )
            ).scalars().all()
            _add(rows)
            proj = db.get(Project, pkg.project_id)
            if proj and proj.short_code:
                project_code = project_code or proj.short_code
        if not result and location_code:
            _add_province_level_fallback(
                result,
                seen,
                role_key=role_key,
                organization_id=organization_id,
                location_code=location_code,
                project_code=project_code,
                db=db,
            )
        return result

    # ── A. Exact location match (field tier — no org-wide location wildcard) ───
    if location_code:
        for proj in ([project_code, None] if project_code else [None]):
            rows = db.execute(
                select(OfficerScope.user_id).where(
                    *base,
                    OfficerScope.location_code == location_code,
                    _optional_project_code_match(db, proj),
                    OfficerScope.package_id.is_(None),
                )
            ).scalars().all()
            _add(rows)
    else:
        for proj in ([project_code, None] if project_code else [None]):
            rows = db.execute(
                select(OfficerScope.user_id).where(
                    *base,
                    OfficerScope.location_code.is_(None),
                    _optional_project_code_match(db, proj),
                    OfficerScope.package_id.is_(None),
                )
            ).scalars().all()
            _add(rows)

    # ── A2. Country-wide scopes on project actor orgs (e.g. ADB donor on KL_ROAD) ─
    if project_code:
        from ticketing.models.project import ProjectOrganization
        from ticketing.services.officer_jurisdiction import is_country_wide_scope
        from ticketing.services.project_routing import load_project_ref

        proj = load_project_ref(db, project_code)
        if proj:
            actor_org_ids = db.execute(
                select(ProjectOrganization.organization_id).where(
                    ProjectOrganization.project_id == proj.project_id
                )
            ).scalars().all()
            for actor_org in actor_org_ids:
                wide_rows = db.execute(
                    select(OfficerScope).where(
                        OfficerScope.role_key == role_key,
                        OfficerScope.organization_id == actor_org,
                        OfficerScope.location_code.is_(None),
                        OfficerScope.project_code.is_(None),
                        OfficerScope.project_id.is_(None),
                        OfficerScope.package_id.is_(None),
                    )
                ).scalars().all()
                for scope in wide_rows:
                    if is_country_wide_scope(db, scope):
                        _add([scope.user_id])

    # ── B. includes_children: ancestor location covers descendants ─────────────
    if location_code:
        ancestors = _location_and_ancestors(location_code, db)
        ancestor_only = [a for a in ancestors if a != location_code]
        if ancestor_only:
            for proj in ([project_code, None] if project_code else [None]):
                rows = db.execute(
                    select(OfficerScope.user_id).where(
                        *base,
                        OfficerScope.location_code.in_(ancestor_only),
                        OfficerScope.includes_children.is_(True),
                        _optional_project_code_match(db, proj),
                        OfficerScope.package_id.is_(None),
                    )
                ).scalars().all()
                _add(rows)

    # ── C. Package-scoped via location (no ticket package_id) ─────────────────
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
                    *base,
                    OfficerScope.package_id.in_(covering_pkg_ids),
                )
            ).scalars().all()
            _add(rows)

    # ── E. Project-wide scope (all packages under project) ────────────────────
    if project_code:
        from ticketing.services.project_routing import load_project_ref

        proj = load_project_ref(db, project_code)
        if proj:
            rows = db.execute(
                select(OfficerScope.user_id).where(
                    *base,
                    OfficerScope.project_id == proj.project_id,
                    OfficerScope.package_id.is_(None),
                )
            ).scalars().all()
            _add(rows)

    if not result and location_code:
        _add_province_level_fallback(
            result,
            seen,
            role_key=role_key,
            organization_id=organization_id,
            location_code=location_code,
            project_code=project_code,
            db=db,
        )

    return result


# ── Officer auto-assignment ───────────────────────────────────────────────────

def auto_assign_officer(
    role_key: str,
    organization_id: str,
    location_code: Optional[str],
    project_code: Optional[str],
    db: Session,
    ticket_package_id: Optional[str] = None,
    *,
    assignment_tier: AssignmentTier = "field",
) -> Optional[str]:
    """
    Find the best officer to assign a ticket to (least-loaded among scoped candidates).
    See _scope_candidates for assignment_tier behaviour.
    """
    from sqlalchemy import func as sqlfunc

    candidates = _scope_candidates(
        role_key,
        organization_id,
        location_code,
        project_code,
        db,
        ticket_package_id=ticket_package_id,
        assignment_tier=assignment_tier,
    )
    if not candidates:
        return None

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

    # OC-04 §5.4 prefer-own-office: among the *already-filtered* candidates, rank first the
    # officers whose office territory covers the ticket location, then least-loaded. A
    # preference, never a filter — the candidate set (and province fallback) is unchanged.
    from ticketing.services.chart_behaviors import territory_covering_user_ids

    covering = territory_covering_user_ids(db, candidates, location_code)

    # (not-covering flag, load, user_id) — ties broken deterministically by user_id so the
    # choice never depends on undefined Postgres row order (would be flaky otherwise).
    return min(
        candidates,
        key=lambda uid: (0 if uid in covering else 1, active_counts.get(uid, 0), uid),
    )


def auto_assign_for_workflow_step(
    step_role_key: str,
    organization_id: str,
    location_code: Optional[str],
    project_code: Optional[str],
    db: Session,
    ticket_package_id: Optional[str] = None,
    *,
    supervisor_role: Optional[str] = None,
) -> Optional[str]:
    """
    Assign using field geographic cascade, then optional fallbacks:
      1. Step role (field tier)
      2. country_l1_fallback when configured for this step role
      3. supervisor_role from the workflow step (e.g. L2 when no L1)
    """
    from ticketing.constants.assignment import country_fallback_for_step_role

    assigned = auto_assign_officer(
        step_role_key,
        organization_id,
        location_code,
        project_code,
        db,
        ticket_package_id=ticket_package_id,
        assignment_tier="field",
    )
    if assigned:
        return assigned

    fallback_role = country_fallback_for_step_role(step_role_key)
    if fallback_role:
        assigned = auto_assign_officer(
            fallback_role,
            organization_id,
            location_code,
            project_code,
            db,
            ticket_package_id=ticket_package_id,
            assignment_tier="country_fallback",
        )
        if assigned:
            return assigned

    if supervisor_role and supervisor_role != step_role_key:
        return auto_assign_officer(
            supervisor_role,
            organization_id,
            location_code,
            project_code,
            db,
            ticket_package_id=ticket_package_id,
            assignment_tier="field",
        )

    return None


def get_teammates(
    role_key: str,
    organization_id: str,
    location_code: Optional[str],
    project_code: Optional[str],
    exclude_user_id: Optional[str],
    db: Session,
    ticket_package_id: Optional[str] = None,
) -> list[str]:
    """Officers eligible for manual reassignment (same pool as auto_assign_officer)."""
    candidates = _scope_candidates(
        role_key,
        organization_id,
        location_code,
        project_code,
        db,
        ticket_package_id=ticket_package_id,
    )
    return [uid for uid in candidates if uid != exclude_user_id]


# ── Step supervisor / assignee helpers (H2-02: moved out of the tickets router) ──

def _find_supervisor_user_id(db: Session, ticket: Ticket) -> Optional[str]:
    """First in-scope holder of the current step's supervisor role, if any."""
    step = get_current_step(ticket, db)
    if not step or not step.supervisor_role:
        return None
    candidates = _scope_candidates(
        role_key=step.supervisor_role,
        organization_id=ticket.organization_id,
        location_code=ticket.location_code,
        project_code=ticket.project_code,
        db=db,
    )
    return candidates[0] if candidates else None


def is_step_assignee_eligible(db: Session, ticket: Ticket, assign_to_user_id: str) -> bool:
    """True when the user is in the current step's role + jurisdiction pool.

    Pure predicate (no HTTP) — the router maps False to a 422. When the ticket has
    no current step there is nothing to validate against, so it returns True.
    """
    step = get_current_step(ticket, db)
    if not step:
        return True
    eligible = get_teammates(
        role_key=step.assigned_role_key,
        organization_id=ticket.organization_id,
        location_code=ticket.location_code,
        project_code=ticket.project_code,
        exclude_user_id=None,
        db=db,
        ticket_package_id=ticket.package_id,
    )
    return assign_to_user_id in eligible
