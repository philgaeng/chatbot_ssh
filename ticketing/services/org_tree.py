"""
Org-tree helpers (OC-01, doc 16 §3.1).

The org forest lives on ``ticketing.organizations.parent_organization_id``. These
helpers answer subtree / ancestry / cycle questions used by the org router (create,
reparent, category inheritance) and — later — by SH-7's org-scoped catalog filter.

Recursive CTEs carry a ``path`` array so a corrupt cycle in the data cannot loop the
query forever (Postgres 13 has no SQL-standard CYCLE clause). Writes are also
cycle-guarded up front by :func:`would_create_cycle`, so a cycle should never reach
the DB in the first place — the path guard is defence in depth.
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ticketing.models.organization import ORG_CATEGORIES, UNIT_TYPES

__all__ = [
    "ORG_CATEGORIES",
    "UNIT_TYPES",
    "INSTITUTIONAL_CATEGORIES",
    "DELEGABLE_CATEGORIES",
    "descendant_org_ids",
    "ancestor_org_ids",
    "would_create_cycle",
    "org_category_matches_unit_type",
]

# Root creation gating (doc 16 §7): institutional roots are super_admin-only;
# third_party (contractors) are delegable. SH-7 enforces the delegation ladder;
# OC-01 exposes the sets so validation/UX can reference them.
INSTITUTIONAL_CATEGORIES = frozenset({"government", "local_government", "donor"})
DELEGABLE_CATEGORIES = frozenset({"third_party"})

# Typical (not enforced) org_category ⇒ unit_type alignment. An off-pattern pairing
# warns, never blocks (doc 16 §3.1) — a division office under a contractor root is a
# legitimate edge case, a typo is not, and only a human can tell them apart.
_CATEGORY_UNIT_ALIGNMENT: dict[str, frozenset[str]] = {
    "government": frozenset(
        {"ministry", "department", "directorate", "provincial_office", "division_office"}
    ),
    "local_government": frozenset({"province_assembly", "municipality"}),
    "donor": frozenset({"development_partner"}),
    "third_party": frozenset({"company"}),
}


def descendant_org_ids(db: Session, org_id: str, *, include_self: bool = True) -> set[str]:
    """Return ``org_id`` and every organization beneath it in the forest.

    Empty set if ``org_id`` does not exist. With ``include_self=False`` the root
    itself is excluded (proper descendants only).
    """
    rows = db.execute(
        sa.text(
            """
            WITH RECURSIVE subtree(organization_id, path) AS (
                SELECT organization_id, ARRAY[organization_id::text]
                FROM ticketing.organizations
                WHERE organization_id = :root
              UNION ALL
                SELECT o.organization_id, s.path || o.organization_id::text
                FROM ticketing.organizations o
                JOIN subtree s ON o.parent_organization_id = s.organization_id
                WHERE NOT o.organization_id::text = ANY(s.path)
            )
            SELECT organization_id FROM subtree
            """
        ),
        {"root": org_id},
    ).scalars().all()
    result = set(rows)
    if not include_self:
        result.discard(org_id)
    return result


def ancestor_org_ids(db: Session, org_id: str, *, include_self: bool = True) -> set[str]:
    """Return ``org_id`` and every organization above it up to its root."""
    rows = db.execute(
        sa.text(
            """
            WITH RECURSIVE ancestors(organization_id, parent_organization_id, path) AS (
                SELECT organization_id, parent_organization_id, ARRAY[organization_id::text]
                FROM ticketing.organizations
                WHERE organization_id = :node
              UNION ALL
                SELECT o.organization_id, o.parent_organization_id, a.path || o.organization_id::text
                FROM ticketing.organizations o
                JOIN ancestors a ON o.organization_id = a.parent_organization_id
                WHERE NOT o.organization_id::text = ANY(a.path)
            )
            SELECT organization_id FROM ancestors
            """
        ),
        {"node": org_id},
    ).scalars().all()
    result = set(rows)
    if not include_self:
        result.discard(org_id)
    return result


def would_create_cycle(db: Session, org_id: str, new_parent_id: str | None) -> bool:
    """True if setting ``org_id``'s parent to ``new_parent_id`` would form a cycle.

    A node cannot be its own parent, nor be re-parented under one of its own
    descendants (that would close a loop).
    """
    if new_parent_id is None:
        return False
    if new_parent_id == org_id:
        return True
    return new_parent_id in descendant_org_ids(db, org_id, include_self=False)


def org_category_matches_unit_type(category: str | None, unit_type: str | None) -> bool:
    """True if the pairing is on-pattern (or nothing to check). Used to *warn*, not block."""
    if not category or not unit_type:
        return True
    return unit_type in _CATEGORY_UNIT_ALIGNMENT.get(category, frozenset())
