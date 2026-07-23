"""
Shared parsing + validation + DB-write logic for org-tree CSV import (OC-01, doc 16 §9).

Split so the same code serves a CLI and the API endpoint (POST /api/v1/organizations/import):
  - :func:`parse_org_csv`  — text → rows (pure)
  - :func:`plan_import`    — whole-file validation, cycle check, category inheritance,
                             topological ordering (pure; no DB)
  - :func:`upsert_organizations` — parents-first idempotent upsert (uses caller's session,
                             flush only — the caller owns the transaction/commit)

The pure functions take everything they need as arguments (including the categories of
any *external* parent orgs already in the DB), so all the interesting logic is unit-
testable without a database. The endpoint does only DB-shaped checks (does this country /
location / external parent exist?) and the final write.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ticketing.models.organization import ORG_CATEGORIES, UNIT_TYPES
from ticketing.utils.organization_identifier import ascii_alnum

REQUIRED_COLUMNS = ("organization_id", "name")
OPTIONAL_COLUMNS = (
    "parent_organization_id",
    "org_category",
    "unit_type",
    "country_code",
    "territory_location_code",
    "territory_includes_children",
    "display_name_ne",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_bool(value: str | None) -> bool:
    return str(value or "").strip().lower() in ("true", "1", "yes", "y")


def _norm_id(raw: str | None) -> str:
    """Normalize an org id the same way the create route does (SH-6: ASCII-only)."""
    if not raw:
        return ""
    return ascii_alnum(raw.strip().upper(), keep_underscore=True)


@dataclass
class OrgImportRow:
    row_num: int
    organization_id: str
    name: str
    parent_organization_id: str | None
    org_category: str | None
    unit_type: str | None
    country_code: str | None
    territory_location_code: str | None
    territory_includes_children: bool
    display_name_ne: str | None


@dataclass
class ImportPlan:
    errors: list[str] = field(default_factory=list)
    ordered_rows: list[OrgImportRow] = field(default_factory=list)
    resolved_categories: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors


def parse_org_csv(content: str) -> list[OrgImportRow]:
    """Parse a flat org CSV into rows. Raises ValueError on an unusable header/empty file."""
    reader = csv.DictReader(io.StringIO(content))
    if reader.fieldnames is None:
        raise ValueError("CSV appears empty — no header row found")
    header = {h.strip() for h in reader.fieldnames}
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        raise ValueError(f"CSV missing required column(s): {', '.join(missing)}")

    rows: list[OrgImportRow] = []
    for row_num, raw in enumerate(reader, start=2):
        # Skip fully blank lines (DictReader yields a dict of empty strings for these).
        if not any((v or "").strip() for v in raw.values()):
            continue
        rows.append(
            OrgImportRow(
                row_num=row_num,
                organization_id=_norm_id(raw.get("organization_id")),
                name=(raw.get("name") or "").strip(),
                parent_organization_id=_norm_id(raw.get("parent_organization_id")) or None,
                org_category=(raw.get("org_category") or "").strip().lower() or None,
                unit_type=(raw.get("unit_type") or "").strip().lower() or None,
                country_code=(raw.get("country_code") or "").strip() or None,
                territory_location_code=(raw.get("territory_location_code") or "").strip() or None,
                territory_includes_children=_parse_bool(raw.get("territory_includes_children")),
                display_name_ne=(raw.get("display_name_ne") or "").strip() or None,
            )
        )
    return rows


def plan_import(
    rows: list[OrgImportRow],
    *,
    external_org_categories: dict[str, str] | None = None,
) -> ImportPlan:
    """Validate the whole file and produce a parents-first ordering + resolved categories.

    ``external_org_categories`` maps the ids of parent orgs that already exist in the DB
    (i.e. are *not* in this file) to their ``org_category``. Any parent that is neither
    in-file nor in this map is reported as "not found". All-or-nothing: if ``errors`` is
    non-empty the caller must write nothing.
    """
    external = external_org_categories or {}
    plan = ImportPlan()
    if not rows:
        plan.errors.append("No organization rows found in file")
        return plan

    # ── per-row field validation + duplicate detection ──
    seen: dict[str, int] = {}
    by_id: dict[str, OrgImportRow] = {}
    for r in rows:
        if not r.organization_id:
            plan.errors.append(f"Row {r.row_num}: organization_id is required")
            continue
        if not r.name:
            plan.errors.append(f"Row {r.row_num}: name is required")
        if r.organization_id in seen:
            plan.errors.append(
                f"Row {r.row_num}: duplicate organization_id '{r.organization_id}' "
                f"(first at row {seen[r.organization_id]})"
            )
            continue
        if r.org_category and r.org_category not in ORG_CATEGORIES:
            plan.errors.append(
                f"Row {r.row_num}: invalid org_category '{r.org_category}' "
                f"(allowed: {', '.join(ORG_CATEGORIES)})"
            )
        if r.unit_type and r.unit_type not in UNIT_TYPES:
            plan.errors.append(
                f"Row {r.row_num}: invalid unit_type '{r.unit_type}' "
                f"(allowed: {', '.join(UNIT_TYPES)})"
            )
        seen[r.organization_id] = r.row_num
        by_id[r.organization_id] = r

    # A row that is its own parent, or references a parent that exists neither in-file
    # nor in the DB, is invalid.
    for r in rows:
        p = r.parent_organization_id
        if p is None:
            continue
        if p == r.organization_id:
            plan.errors.append(f"Row {r.row_num}: organization is its own parent")
        elif p not in by_id and p not in external:
            plan.errors.append(
                f"Row {r.row_num}: parent_organization_id '{p}' not found (not in file or DB)"
            )

    if plan.errors:
        return plan  # don't attempt ordering/inheritance on a structurally broken file

    # ── cycle detection over in-file edges (external parents are existing DB roots and
    #    cannot close a loop with brand-new rows) + topological order (parents first) ──
    in_file = set(by_id)
    ordered: list[OrgImportRow] = []
    state: dict[str, int] = {}  # 0=unvisited, 1=on-stack, 2=done

    def visit(node: str, trail: list[str]) -> bool:
        st = state.get(node, 0)
        if st == 2:
            return True
        if st == 1:
            cycle = trail[trail.index(node):] + [node]
            plan.errors.append("Cycle detected among organizations: " + " → ".join(cycle))
            return False
        state[node] = 1
        parent = by_id[node].parent_organization_id
        if parent in in_file:
            if not visit(parent, trail + [node]):
                return False
        state[node] = 2
        ordered.append(by_id[node])
        return True

    for oid in by_id:
        if state.get(oid, 0) != 2:
            if not visit(oid, []):
                return plan  # cycle — stop, all-or-nothing

    # ── resolve org_category (root explicit; children inherit; explicit-but-mismatched
    #    is an error) in the now parents-first order ──
    resolved: dict[str, str] = {}
    for r in ordered:
        parent = r.parent_organization_id
        if parent is None:
            if not r.org_category:
                plan.errors.append(
                    f"Row {r.row_num}: root organization '{r.organization_id}' "
                    f"requires an org_category"
                )
                continue
            resolved[r.organization_id] = r.org_category
        else:
            parent_cat = resolved.get(parent) or external.get(parent)
            if parent_cat is None:
                # Should not happen after the checks above, but guard anyway.
                plan.errors.append(
                    f"Row {r.row_num}: could not resolve category from parent '{parent}'"
                )
                continue
            if r.org_category and r.org_category != parent_cat:
                plan.errors.append(
                    f"Row {r.row_num}: org_category '{r.org_category}' conflicts with "
                    f"inherited '{parent_cat}' from parent '{parent}' (children inherit the "
                    f"root's category)"
                )
                continue
            resolved[r.organization_id] = parent_cat

    if plan.errors:
        return plan
    plan.ordered_rows = ordered
    plan.resolved_categories = resolved
    return plan


def upsert_organizations(
    ordered_rows: list[OrgImportRow],
    resolved_categories: dict[str, str],
    db: Any,  # sqlalchemy.orm.Session
) -> int:
    """Idempotent parents-first upsert into ticketing.organizations.

    ``ordered_rows`` must be the topologically ordered list from :func:`plan_import`
    (parents before children) so the self-FK is satisfied inside the single transaction.
    Uses the caller's session and flushes only — the caller commits.
    """
    import sqlalchemy as sa

    sql = sa.text(
        """
        INSERT INTO ticketing.organizations
            (organization_id, name, parent_organization_id, org_category, unit_type,
             country_code, territory_location_code, territory_includes_children,
             display_name_ne, is_active, default_language, created_at, updated_at)
        VALUES
            (:organization_id, :name, :parent_organization_id, :org_category, :unit_type,
             :country_code, :territory_location_code, :territory_includes_children,
             :display_name_ne, true, 'ne', :now, :now)
        ON CONFLICT (organization_id) DO UPDATE SET
            name                        = EXCLUDED.name,
            parent_organization_id      = EXCLUDED.parent_organization_id,
            org_category                = EXCLUDED.org_category,
            unit_type                   = EXCLUDED.unit_type,
            country_code                = EXCLUDED.country_code,
            territory_location_code     = EXCLUDED.territory_location_code,
            territory_includes_children = EXCLUDED.territory_includes_children,
            display_name_ne             = EXCLUDED.display_name_ne,
            updated_at                  = EXCLUDED.updated_at
        """
    )
    now = _now()
    for r in ordered_rows:
        db.execute(
            sql,
            {
                "organization_id": r.organization_id,
                "name": r.name,
                "parent_organization_id": r.parent_organization_id,
                "org_category": resolved_categories[r.organization_id],
                "unit_type": r.unit_type,
                "country_code": r.country_code,
                "territory_location_code": r.territory_location_code,
                "territory_includes_children": r.territory_includes_children,
                "display_name_ne": r.display_name_ne,
                "now": now,
            },
        )
    db.flush()  # within the caller's transaction; caller commits
    return len(ordered_rows)


CSV_TEMPLATE = """\
organization_id,name,parent_organization_id,org_category,unit_type,country_code,territory_location_code,territory_includes_children,display_name_ne
MOPIT,Ministry of Physical Infrastructure and Transport,,government,ministry,NP,,,भौतिक पूर्वाधार तथा यातायात मन्त्रालय
DOR,Department of Roads,MOPIT,government,department,NP,,,सडक विभाग
DOR_JHA,Jhapa Division Road Office,DOR,government,division_office,NP,P1_JHA,true,झापा डिभिजन सडक कार्यालय
"""
