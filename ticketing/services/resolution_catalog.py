# SPDX-License-Identifier: Apache-2.0

"""The resolution-action catalog and each workflow's list from it (GRM-116, model: DESIGN §3.1.1).

**This module is the only writer of ``workflow_resolution_actions`` and the only way to create a
``resolution_actions`` row.** Every path — create, clone, save-as-template, seeds — goes through it,
so no new caller can skip the rules:

1. **Nothing is global** (Q-10). Every action belongs to one organization. An action owned by a
   **ministry** (a top organization) is *shared*; one owned below its ministry is *local* and must
   **count as** one shared action of that same ministry, so national totals stay whole.
2. **Usable** = the action's organization is the workflow's organization or one above it. A workflow
   with no organization can use nothing.
3. **A sensitive workflow lists nothing** — a SEAH case records neither what was done nor who did it
   (DESIGN §3.1.3).
4. **At most ``MAX_RESOLUTION_ACTIONS``** per workflow and template.
5. **A published non-sensitive workflow lists at least one.** A draft or template may be empty — a new
   one starts that way — and publishing it is refused (``routers/workflows.py``).
6. **Lists are copied, never inherited**: a later change to the source does not reach the copy.

⚠ Usability is checked against the **workflow's organization**, not the viewer's scope — so this is
not ``admin_access.apply_catalog_scope``, which filters by who is looking.
"""
from __future__ import annotations

from typing import Iterable, Optional, Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ticketing.constants.resolution import MAX_RESOLUTION_ACTIONS, STARTER_ACTIONS
from ticketing.models.organization import Organization
from ticketing.models.resolution_action import ResolutionAction, WorkflowResolutionAction
from ticketing.models.ticket import Ticket
from ticketing.models.workflow import WorkflowDefinition
from ticketing.services.org_tree import descendant_org_ids


class ResolutionCatalogError(ValueError):
    """A list or an action that breaks one of the module's rules. Callers map it to a 422."""


def is_sensitive_workflow(workflow: WorkflowDefinition) -> bool:
    # Same rule as admin_access.workflow_track_from_type, restated so the officer-action engine
    # can import this module without pulling in the admin/HTTP layer.
    return (workflow.workflow_type or "").lower() == "seah"


def ministry_of(db: Session, organization_id: str) -> Optional[str]:
    """The top organization (no parent) above ``organization_id`` — itself when it is one.
    None if the organization does not exist. Cycle-guarded."""
    seen: set[str] = set()
    current = organization_id
    while current and current not in seen:
        seen.add(current)
        org = db.get(Organization, current)
        if org is None:
            return None
        if not org.parent_organization_id:
            return org.organization_id
        current = org.parent_organization_id
    return None


def is_shared(db: Session, action: ResolutionAction) -> bool:
    return ministry_of(db, action.owner_organization_id) == action.owner_organization_id


def available_to_workflow(db: Session, action: ResolutionAction, workflow: WorkflowDefinition) -> bool:
    if not workflow.owner_organization_id:
        return False
    return workflow.owner_organization_id in descendant_org_ids(
        db, action.owner_organization_id, include_self=True
    )


def create_action(
    db: Session,
    *,
    code: str,
    label: str,
    default_wording: str,
    owner_organization_id: Optional[str],
    counts_as_code: Optional[str] = None,
    created_by_user_id: Optional[str] = None,
) -> ResolutionAction:
    """Add an action to the catalog, enforcing rule 1. Raises :class:`ResolutionCatalogError`."""
    if not owner_organization_id:
        raise ResolutionCatalogError("A resolution action must belong to an organization.")
    ministry = ministry_of(db, owner_organization_id)
    if ministry is None:
        raise ResolutionCatalogError(f"Unknown organization: {owner_organization_id}")
    if db.get(ResolutionAction, code) is not None:
        raise ResolutionCatalogError(f"Resolution action {code} already exists.")

    if ministry == owner_organization_id:
        if counts_as_code:
            raise ResolutionCatalogError(
                "A national action belongs to its ministry and does not count as another action."
            )
    else:
        if not counts_as_code:
            raise ResolutionCatalogError(
                "A local action must say which national action it counts as in national reports."
            )
        target = db.get(ResolutionAction, counts_as_code)
        if target is None:
            raise ResolutionCatalogError(f"Unknown resolution action: {counts_as_code}")
        if target.owner_organization_id != ministry:
            raise ResolutionCatalogError(
                f"{counts_as_code} is not a national action of this organization's ministry."
            )

    action = ResolutionAction(
        code=code,
        label=label,
        default_wording=default_wording,
        owner_organization_id=owner_organization_id,
        counts_as_code=counts_as_code if ministry != owner_organization_id else None,
        is_active=True,
        created_by_user_id=created_by_user_id,
    )
    db.add(action)
    db.flush()
    return action


def ensure_starter_actions(db: Session, ministry_id: str) -> None:
    """Create the starter actions as shared actions of ``ministry_id`` where missing (seed path, for
    a database the migration found no ministry on). An existing code is left as it is."""
    for code, label, wording in STARTER_ACTIONS:
        if db.get(ResolutionAction, code) is None:
            create_action(
                db, code=code, label=label, default_wording=wording,
                owner_organization_id=ministry_id,
            )


def set_workflow_actions(db: Session, workflow: WorkflowDefinition, codes: Sequence[str]) -> None:
    """Replace ``workflow``'s list with ``codes``, in that order. Raises
    :class:`ResolutionCatalogError` — and writes nothing — if any rule is broken."""
    codes = list(codes)
    if is_sensitive_workflow(workflow):
        if codes:
            raise ResolutionCatalogError(
                "A sensitive workflow does not record a resolution action, so none can be added."
            )
    elif not codes and workflow.status == "published" and not workflow.is_template:
        raise ResolutionCatalogError(
            "A published workflow needs at least one resolution action."
        )
    if len(codes) > MAX_RESOLUTION_ACTIONS:
        raise ResolutionCatalogError(
            f"A workflow can offer at most {MAX_RESOLUTION_ACTIONS} resolution actions."
        )
    if len(set(codes)) != len(codes):
        raise ResolutionCatalogError("The same resolution action is listed twice.")

    actions = {
        a.code: a
        for a in db.execute(select(ResolutionAction).where(ResolutionAction.code.in_(codes))).scalars()
    } if codes else {}
    for code in codes:
        action = actions.get(code)
        if action is None:
            raise ResolutionCatalogError(f"Unknown resolution action: {code}")
        if not action.is_active:
            raise ResolutionCatalogError(f"Resolution action {code} is no longer in use.")
        if not available_to_workflow(db, action, workflow):
            raise ResolutionCatalogError(
                f"'{action.label}' belongs to an organization this workflow is not part of."
            )

    db.flush()  # the workflow row must exist before its list references it
    db.execute(
        delete(WorkflowResolutionAction).where(WorkflowResolutionAction.workflow_id == workflow.workflow_id)
    )
    for i, code in enumerate(codes):
        db.add(WorkflowResolutionAction(workflow_id=workflow.workflow_id, code=code, sort_order=(i + 1) * 10))
    db.flush()


def selected_codes(db: Session, workflow_id: str, *, active_only: bool = True) -> list[str]:
    stmt = (
        select(WorkflowResolutionAction.code)
        .join(ResolutionAction, ResolutionAction.code == WorkflowResolutionAction.code)
        .where(WorkflowResolutionAction.workflow_id == workflow_id)
        .order_by(WorkflowResolutionAction.sort_order)
    )
    if active_only:
        stmt = stmt.where(ResolutionAction.is_active.is_(True))
    return list(db.execute(stmt).scalars())


def actions_unusable_by(db: Session, workflow_id: str, organization_id: str) -> list[ResolutionAction]:
    """The actions on a workflow's list that ``organization_id`` could not use — what blocks moving
    the workflow there (GRM-122). Inactive ones included: they are still on the list."""
    codes = selected_codes(db, workflow_id, active_only=False)
    if not codes:
        return []
    actions = db.execute(select(ResolutionAction).where(ResolutionAction.code.in_(codes))).scalars().all()
    by_code = {a.code: a for a in actions}
    blocked = []
    for code in codes:
        action = by_code[code]
        if organization_id not in descendant_org_ids(db, action.owner_organization_id, include_self=True):
            blocked.append(action)
    return blocked


def copy_workflow_actions(db: Session, source_workflow_id: str, target: WorkflowDefinition) -> None:
    """Give ``target`` a **copy** of the source's list — for clone, create-from-template and
    save-as-template. Refused (nothing written) if the target's organization cannot use one of the
    actions: a copy never silently drops what its author was shown."""
    set_workflow_actions(db, target, selected_codes(db, source_workflow_id))


def options_for_workflow(db: Session, workflow_id: Optional[str]) -> list[dict]:
    """The actions an officer may choose on a case in this workflow, in order."""
    if not workflow_id:
        return []
    rows = db.execute(
        select(ResolutionAction)
        .join(WorkflowResolutionAction, WorkflowResolutionAction.code == ResolutionAction.code)
        .where(
            WorkflowResolutionAction.workflow_id == workflow_id,
            ResolutionAction.is_active.is_(True),
        )
        .order_by(WorkflowResolutionAction.sort_order)
    ).scalars()
    return [{"code": a.code, "label": a.label, "default_wording": a.default_wording} for a in rows]


def options_for_ticket(db: Session, ticket: Ticket) -> list[dict]:
    return options_for_workflow(db, ticket.current_workflow_id)


def action_labels(db: Session, codes: Iterable[str]) -> dict[str, str]:
    """Catalog labels by code, inactive actions included — for events written before labels were
    snapshotted into the payload."""
    wanted = {c for c in codes if c}
    if not wanted:
        return {}
    return dict(
        db.execute(
            select(ResolutionAction.code, ResolutionAction.label).where(ResolutionAction.code.in_(wanted))
        ).all()
    )


def national_action_labels(db: Session, codes: Iterable[str]) -> dict[str, str]:
    """Code → the label of the **shared** action it counts as nationally (GRM-118): the action itself
    when shared (``counts_as_code`` NULL), its ``counts_as_code`` when local. Read through the **current**
    catalog, so correcting what a local action counts as corrects past totals. One query per hop."""
    wanted = {c for c in codes if c}
    if not wanted:
        return {}
    national_of = {
        code: counts_as or code
        for code, counts_as in db.execute(
            select(ResolutionAction.code, ResolutionAction.counts_as_code).where(ResolutionAction.code.in_(wanted))
        ).all()
    }
    labels = action_labels(db, national_of.values())
    return {code: labels.get(national, national) for code, national in national_of.items()}


def event_action_label(db: Session, payload: Optional[dict], *, labels: Optional[dict[str, str]] = None) -> str:
    """The label a resolution event records: its snapshot, else the catalog's label for its code,
    else the code itself, else "" (a sensitive-workflow case records none)."""
    payload = payload or {}
    snapshot = payload.get("resolution_category_label")
    if snapshot:
        return str(snapshot)
    code = payload.get("resolution_category")
    if not code:
        return ""
    if labels is None:
        labels = action_labels(db, [code])
    return labels.get(code, str(code))
