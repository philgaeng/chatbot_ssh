"""
OC-04 — chart-driven behaviors (doc 16 §5). Read-only helpers only: the org chart drives
display, visibility, and a ranking *preference* — never an access-control or routing
decision (those stay in user_roles / officer_scopes / the workflow engine).

Every SEAH-sensitive caller (Watching visibility §5.3, escalation-notify §5.5) applies the
SEAH predicate inline; :func:`user_holds_seah_role` is the "unless they independently hold a
SEAH role" guard.
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ticketing.models.officer_position import OfficerPosition
from ticketing.models.officer_scope import OfficerScope
from ticketing.models.organization import Organization
from ticketing.models.position_type import PositionType
from ticketing.services.org_tree import descendant_org_ids


def user_holds_seah_role(db: Session, user_id: str) -> bool:
    """True if the officer independently holds a SEAH operational role — the guard that lets
    a SEAH-holding supervisor/viewer see a SEAH case that reporting lines otherwise hide."""
    from ticketing.models.user import SEAH_ROLES
    from ticketing.services.admin_access import load_effective_role_keys

    return bool(set(load_effective_role_keys(db, user_id)) & SEAH_ROLES)


def user_can_see_seah(db: Session, user_id: str) -> bool:
    """R1 SEAH-leak guard for **notification recipients** (arbitrary user_ids): True if the
    user may see sensitive cases at all. The per-user_id mirror of ``CurrentUser.can_see_seah``
    — so it follows the same rule: **cast membership only**. Use this before addressing any
    notification/@mention/GRC-convene event about a ticket to a user other than the request user.

    DECISION-sensitive-workflows §3 (2026-08-02) dropped ``BOTH_WORKFLOWS_ROLES``
    (``super_admin`` / ``adb_hq_exec``) from this set: an oversight role is not a reason to be
    told a sensitive grievance exists. A donor's safeguards staff who need them are cast on the
    workflow (observer tier), which this predicate then matches."""
    from ticketing.models.user import SEAH_ROLES
    from ticketing.services.admin_access import load_effective_role_keys
    from ticketing.services.seah_visibility import user_is_seah_track_member

    role_keys = set(load_effective_role_keys(db, user_id))
    if role_keys & SEAH_ROLES:
        return True
    return user_is_seah_track_member(db, role_keys)


def visible_report_user_ids(db: Session, user_id: str) -> set[str]:
    """Officers who are ``user_id``'s reports for **visibility** (doc 16 §5.3), via the org
    chart bounded by each of the viewer's position types' ``visibility_mode``:
    ``none`` → nobody; ``direct_reports`` → officers at direct child org units;
    ``subtree`` → officers anywhere in the org subtree. Org-hierarchy oversight only — this
    is NOT grievance supervision (that is the per-(project,step) resolver)."""
    rows = db.execute(
        sa.select(OfficerPosition.organization_id, PositionType.visibility_mode)
        .join(PositionType, PositionType.position_type_id == OfficerPosition.position_type_id)
        .where(OfficerPosition.user_id == user_id, OfficerPosition.is_active.is_(True))
    ).all()

    report_orgs: set[str] = set()
    for org_id, vmode in rows:
        if vmode == "subtree":
            report_orgs |= descendant_org_ids(db, org_id, include_self=False)
        elif vmode == "direct_reports":
            report_orgs |= set(
                db.execute(
                    sa.select(Organization.organization_id).where(
                        Organization.parent_organization_id == org_id
                    )
                ).scalars().all()
            )
        # "none" → contributes nothing

    if not report_orgs:
        return set()
    reports = set(
        db.execute(
            sa.select(OfficerPosition.user_id).where(
                OfficerPosition.organization_id.in_(report_orgs),
                OfficerPosition.is_active.is_(True),
            )
        ).scalars().all()
    )
    reports.discard(user_id)
    return reports


def _location_and_ancestors(db: Session, location_code: str) -> set[str]:
    rows = db.execute(
        sa.text(
            """
            WITH RECURSIVE ancestors AS (
                SELECT location_code, parent_location_code
                FROM ticketing.locations WHERE location_code = :lc
              UNION ALL
                SELECT l.location_code, l.parent_location_code
                FROM ticketing.locations l
                JOIN ancestors a ON l.location_code = a.parent_location_code
            )
            SELECT location_code FROM ancestors
            """
        ),
        {"lc": location_code},
    ).scalars().all()
    return set(rows)


def territory_covering_user_ids(
    db: Session, candidates: list[str], location_code: str | None
) -> set[str]:
    """Subset of ``candidates`` whose office territory covers ``location_code`` (doc 16
    §5.4) — an org's ``territory_location_code`` equals the ticket location, or (with
    ``territory_includes_children``) is an ancestor of it. A ranking *preference* only;
    never removes a candidate."""
    if not candidates or not location_code:
        return set()
    ancestors = _location_and_ancestors(db, location_code)
    orgs = db.execute(
        sa.select(
            Organization.organization_id,
            Organization.territory_location_code,
            Organization.territory_includes_children,
        ).where(Organization.territory_location_code.isnot(None))
    ).all()
    covering_orgs = {
        oid for (oid, terr, inc) in orgs
        if terr == location_code or (inc and terr in ancestors)
    }
    if not covering_orgs:
        return set()
    cand = set(candidates)
    users = set(
        db.execute(
            sa.select(OfficerPosition.user_id).where(
                OfficerPosition.user_id.in_(cand),
                OfficerPosition.organization_id.in_(covering_orgs),
                OfficerPosition.is_active.is_(True),
            )
        ).scalars().all()
    )
    users |= set(
        db.execute(
            sa.select(OfficerScope.user_id).where(
                OfficerScope.user_id.in_(cand),
                OfficerScope.organization_id.in_(covering_orgs),
            )
        ).scalars().all()
    )
    return users & cand
