"""Resolve project workflow from intake_route (story_main) + optional classification re-route."""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from ticketing.constants.workflow_routing import (
    INTAKE_ROUTE_NEW_GRIEVANCE,
    INTAKE_ROUTE_PRIORITY,
    INTAKE_ROUTE_ROAD_HAZARD,
    INTAKE_ROUTE_SEAH,
    intake_route_from_payload,
    normalize_classification,
    normalize_intake_route,
)
from ticketing.models.project_workflow import ProjectWorkflow
from ticketing.models.workflow import WorkflowDefinition
from ticketing.services.grievance_categories_catalog import load_grievance_categories_catalog
from ticketing.services.project_workflows import list_project_workflows

logger = logging.getLogger(__name__)

_SEAH_CLASSIFICATIONS = frozenset(
    normalize_classification(c)
    for c in (
        "Gender",
        "Gender, Social",
        "Malicious Behavior",
        "Malicious Behavior, Environmental",
    )
)
_ROAD_HAZARD_CLASSIFICATION = normalize_classification("Road Hazard")


def _category_catalog_index(db: Session) -> dict[str, dict]:
    """Map category_key (case variants) → catalog entry."""
    catalog = load_grievance_categories_catalog(db)
    out: dict[str, dict] = {}
    for entry in catalog.get("categories") or []:
        key = (entry.get("category_key") or "").strip()
        if not key:
            continue
        out[key] = entry
        out[key.lower()] = entry
    return out


def _default_intake_route_for_entry(entry: dict) -> str:
    explicit = normalize_intake_route(entry.get("intake_route"))
    if explicit:
        return explicit
    cls = normalize_classification(entry.get("classification") or "")
    if cls == _ROAD_HAZARD_CLASSIFICATION:
        return INTAKE_ROUTE_ROAD_HAZARD
    if cls in _SEAH_CLASSIFICATIONS:
        return INTAKE_ROUTE_SEAH
    return INTAKE_ROUTE_NEW_GRIEVANCE


def intake_route_from_categories(db: Session, grievance_categories: Any) -> str:
    """Derive effective intake_route from selected category keys (tie-break: SEAH > road > safeguards)."""
    routes: list[str] = []
    index = _category_catalog_index(db)
    for key in _coerce_category_keys(grievance_categories):
        entry = index.get(key) or index.get(key.lower())
        if entry:
            routes.append(_default_intake_route_for_entry(entry))
    if not routes:
        return INTAKE_ROUTE_NEW_GRIEVANCE
    return min(routes, key=lambda r: INTAKE_ROUTE_PRIORITY.get(r, 99))


def effective_intake_route_for_reroute(
    db: Session,
    grievance_categories: Any,
    *,
    stored_intake_route: str | None,
) -> str:
    """
    Re-route only from safeguards (new_grievance) path when categories imply another stream.
    SEAH and road-hazard menu paths stay on their original intake_route.
    """
    stored = normalize_intake_route(stored_intake_route)
    if stored and stored != INTAKE_ROUTE_NEW_GRIEVANCE:
        return stored
    return intake_route_from_categories(db, grievance_categories)


def _coerce_category_keys(grievance_categories: Any) -> list[str]:
    if grievance_categories is None:
        return []
    cats = grievance_categories
    if isinstance(cats, str):
        raw = cats.strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
            cats = parsed if isinstance(parsed, list) else [raw]
        except json.JSONDecodeError:
            cats = [c.strip() for c in raw.split(",") if c.strip()]
    if not isinstance(cats, list):
        return []
    return [str(item).strip() for item in cats if str(item).strip()]


def classifications_from_categories(
    db: Session,
    grievance_categories: Any,
) -> set[str]:
    """Derive taxonomy classifications from ticket category keys."""
    index = _category_catalog_index(db)
    found: set[str] = set()
    for key in _coerce_category_keys(grievance_categories):
        entry = index.get(key) or index.get(key.lower())
        if not entry:
            continue
        raw = (entry.get("classification") or "").strip()
        if raw:
            found.add(normalize_classification(raw))
    return found


def list_catalog_classifications(db: Session) -> list[str]:
    catalog = load_grievance_categories_catalog(db)
    seen: dict[str, str] = {}
    for entry in catalog.get("categories") or []:
        raw = (entry.get("classification") or "").strip()
        if not raw:
            continue
        norm = normalize_classification(raw)
        if norm not in seen:
            seen[norm] = raw
    return sorted(seen.values(), key=lambda s: s.lower())


def _binding_classifications(row: ProjectWorkflow) -> set[str]:
    raw = row.classifications or []
    return {normalize_classification(c) for c in raw if str(c).strip()}


def _workflow_for_binding(db: Session, row: ProjectWorkflow) -> WorkflowDefinition | None:
    return db.get(WorkflowDefinition, row.workflow_id)


def pick_project_workflow_binding(
    bindings: list[ProjectWorkflow],
    *,
    intake_route: str | None,
    ticket_classifications: set[str] | None = None,
    use_classification_rules: bool = False,
) -> ProjectWorkflow | None:
    """
    Select the best project workflow binding.

    Priority:
      1. intake_route match on non-default rows
      2. (re-route only) classification match on non-default rows
      3. Default row (is_default=true)
    """
    if not bindings:
        return None

    defaults = [b for b in bindings if b.is_default]
    non_default = [b for b in bindings if not b.is_default]
    route = normalize_intake_route(intake_route)

    if route:
        route_matches = [
            r
            for r in non_default
            if normalize_intake_route(r.intake_route) == route
        ]
        if route_matches:
            return sorted(route_matches, key=lambda r: r.sort_order)[0]

    if use_classification_rules and ticket_classifications:
        class_matches: list[ProjectWorkflow] = []
        for row in non_default:
            rules = _binding_classifications(row)
            if rules and ticket_classifications & rules:
                class_matches.append(row)
        if class_matches:
            return min(class_matches, key=lambda r: (len(_binding_classifications(r)), r.sort_order))

    if defaults:
        return sorted(defaults, key=lambda r: r.sort_order)[0]

    return sorted(bindings, key=lambda r: r.sort_order)[0]


def resolve_project_workflow(
    db: Session,
    project_id: str,
    *,
    grievance_categories: Any = None,
    intake_route: str | None = None,
    legacy_is_seah: bool = False,
    use_classification_rules: bool = False,
) -> WorkflowDefinition | None:
    bindings = list_project_workflows(db, project_id)
    if not bindings:
        return None

    route = intake_route_from_payload(
        intake_route=intake_route,
        legacy_is_seah=legacy_is_seah,
    )
    if not route and not use_classification_rules:
        route = intake_route_from_categories(db, grievance_categories)

    ticket_cls = classifications_from_categories(db, grievance_categories)

    picked = pick_project_workflow_binding(
        bindings,
        intake_route=route,
        ticket_classifications=ticket_cls,
        use_classification_rules=use_classification_rules,
    )
    if not picked:
        return None
    return _workflow_for_binding(db, picked)


def workflow_is_seah(workflow: WorkflowDefinition | None) -> bool:
    if workflow is None:
        return False
    return (workflow.workflow_type or "").lower() == "seah"


def uncovered_classifications(
    db: Session,
    bindings: list[ProjectWorkflow],
) -> list[str]:
    """Catalog classifications not covered by any non-default binding (for go-live warn)."""
    all_cls = {normalize_classification(c) for c in list_catalog_classifications(db)}
    covered: set[str] = set()
    for row in bindings:
        if row.is_default:
            continue
        covered |= _binding_classifications(row)
    missing_norm = all_cls - covered
    if not missing_norm:
        return []
    catalog = load_grievance_categories_catalog(db)
    display: dict[str, str] = {}
    for entry in catalog.get("categories") or []:
        raw = (entry.get("classification") or "").strip()
        if raw:
            display[normalize_classification(raw)] = raw
    return sorted({display.get(n, n) for n in missing_norm})
