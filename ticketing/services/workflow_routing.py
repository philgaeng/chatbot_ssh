"""Resolve project workflow from classifications + intake signals."""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from ticketing.constants.workflow_routing import (
    normalize_classification,
    intake_signals_from_payload,
)
from ticketing.models.project_workflow import ProjectWorkflow
from ticketing.models.workflow import WorkflowDefinition
from ticketing.services.grievance_categories_catalog import load_grievance_categories_catalog
from ticketing.services.project_workflows import list_project_workflows

logger = logging.getLogger(__name__)


def _category_key_index(db: Session) -> dict[str, str]:
    """Map category_key → normalized classification."""
    catalog = load_grievance_categories_catalog(db)
    out: dict[str, str] = {}
    for entry in catalog.get("categories") or []:
        key = (entry.get("category_key") or "").strip()
        cls = normalize_classification(entry.get("classification") or "")
        if key and cls:
            out[key] = cls
            out[key.lower()] = cls
    return out


def classifications_from_categories(
    db: Session,
    grievance_categories: Any,
) -> set[str]:
    """Derive taxonomy classifications from ticket category keys."""
    if grievance_categories is None:
        return set()
    cats = grievance_categories
    if isinstance(cats, str):
        raw = cats.strip()
        if not raw:
            return set()
        try:
            parsed = json.loads(raw)
            cats = parsed if isinstance(parsed, list) else [raw]
        except json.JSONDecodeError:
            cats = [c.strip() for c in raw.split(",") if c.strip()]
    if not isinstance(cats, list):
        return set()

    index = _category_key_index(db)
    found: set[str] = set()
    for item in cats:
        key = str(item).strip()
        if not key:
            continue
        cls = index.get(key) or index.get(key.lower())
        if cls:
            found.add(cls)
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


def _binding_intake_routes(row: ProjectWorkflow) -> set[str]:
    raw = row.intake_routes or []
    return {str(r).strip().lower() for r in raw if str(r).strip()}


def _workflow_for_binding(db: Session, row: ProjectWorkflow) -> WorkflowDefinition | None:
    return db.get(WorkflowDefinition, row.workflow_id)


def pick_project_workflow_binding(
    bindings: list[ProjectWorkflow],
    db: Session,
    *,
    ticket_classifications: set[str],
    intake_signals: set[str],
) -> ProjectWorkflow | None:
    """
    Select the best project workflow binding.

    Priority:
      1. Intake signal match (non-default rows; narrowest intake_routes list wins)
      2. Classification match (non-default; smallest classification rule set wins)
      3. Default row (is_default=true)
    """
    if not bindings:
        return None

    defaults = [b for b in bindings if b.is_default]
    non_default = [b for b in bindings if not b.is_default]

    intake_matches: list[ProjectWorkflow] = []
    for row in non_default:
        routes = _binding_intake_routes(row)
        if routes and intake_signals & routes:
            intake_matches.append(row)

    if intake_matches:
        return min(intake_matches, key=lambda r: (len(_binding_intake_routes(r)), r.sort_order))

    if ticket_classifications:
        class_matches: list[ProjectWorkflow] = []
        for row in non_default:
            rules = _binding_classifications(row)
            if rules and ticket_classifications & rules:
                class_matches.append(row)
        if class_matches:
            return min(class_matches, key=lambda r: (len(_binding_classifications(r)), r.sort_order))

    if defaults:
        return sorted(defaults, key=lambda r: r.sort_order)[0]

    # No default flagged — fall back to first binding
    return sorted(bindings, key=lambda r: r.sort_order)[0]


def resolve_project_workflow(
    db: Session,
    project_id: str,
    *,
    grievance_categories: Any = None,
    intake_route: str | None = None,
    intake_fast_path: str | None = None,
    legacy_is_seah: bool = False,
) -> WorkflowDefinition | None:
    bindings = list_project_workflows(db, project_id)
    if not bindings:
        return None

    ticket_cls = classifications_from_categories(db, grievance_categories)
    signals = intake_signals_from_payload(
        intake_route=intake_route,
        intake_fast_path=intake_fast_path,
        legacy_is_seah=legacy_is_seah,
    )

    picked = pick_project_workflow_binding(
        bindings,
        db,
        ticket_classifications=ticket_cls,
        intake_signals=signals,
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
    # Warn even when a default workflow exists — admin should map explicitly.
    catalog = load_grievance_categories_catalog(db)
    display: dict[str, str] = {}
    for entry in catalog.get("categories") or []:
        raw = (entry.get("classification") or "").strip()
        if raw:
            display[normalize_classification(raw)] = raw
    return sorted({display.get(n, n) for n in missing_norm})
