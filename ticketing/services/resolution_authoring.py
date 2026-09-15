# SPDX-License-Identifier: Apache-2.0

"""Authoring resolution actions from a workflow's panel (GRM-119, model: DESIGN §3.1.1, Q-10).

One place: a panel in the workflow editor. An admin chooses up to 8 actions for a workflow, creates a
new one into it, and edits an action. **The admin never chooses an owner** — a new action belongs to the
workflow's organization, or to its ministry when the admin makes it a national action. A local action
must say which of its ministry's shared actions it counts as in national reports.

Who may do what (all enforced here; the UI only renders the flags it is given). *Reach* is the
organizations an admin administers on the standard track; a platform admin reaches everything:

| Action | Allowed when |
|---|---|
| Change a workflow's list (add, remove, reorder, create into it) | the workflow's organization is in reach · not sensitive · ≤ 8 |
| Create a *national* action | as above, plus the workflow's ministry is in reach |
| Edit an action | the action's owner is in reach |

Separate from ``resolution_catalog`` on purpose: that module is imported by the officer-action engine
and stays free of the admin/HTTP layer; this one is the admin side.
"""
from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ticketing.constants.resolution import MAX_RESOLUTION_ACTIONS
from ticketing.models.resolution_action import ResolutionAction, WorkflowResolutionAction
from ticketing.models.workflow import WorkflowDefinition
from ticketing.services.admin_access import can_admin_org
from ticketing.services.org_tree import ancestor_org_ids
from ticketing.services.resolution_catalog import (
    ResolutionCatalogError,
    create_action,
    is_sensitive_workflow,
    ministry_of,
    selected_codes,
    set_workflow_actions,
)

if TYPE_CHECKING:
    from ticketing.api.dependencies import CurrentUser

TRACK = "standard"  # sensitive workflows list no action, so only the standard track authors


class ResolutionPermissionError(PermissionError):
    """The caller may not do this. Routers map it to a 403."""


def can_change_list(db: Session, user: "CurrentUser", workflow: WorkflowDefinition) -> bool:
    return (
        not is_sensitive_workflow(workflow)
        and bool(workflow.owner_organization_id)
        and can_admin_org(db, user, workflow.owner_organization_id, TRACK)
    )


def can_edit_action(db: Session, user: "CurrentUser", action: ResolutionAction) -> bool:
    return can_admin_org(db, user, action.owner_organization_id, TRACK)


def can_create_national(db: Session, user: "CurrentUser", workflow: WorkflowDefinition) -> bool:
    if not can_change_list(db, user, workflow):
        return False
    ministry = ministry_of(db, workflow.owner_organization_id)
    return bool(ministry) and can_admin_org(db, user, ministry, TRACK)


def used_by_counts(db: Session, codes: list[str]) -> dict[str, int]:
    if not codes:
        return {}
    return dict(db.execute(
        select(WorkflowResolutionAction.code, func.count())
        .where(WorkflowResolutionAction.code.in_(codes))
        .group_by(WorkflowResolutionAction.code)
    ).all())


def national_choices(db: Session, workflow: WorkflowDefinition) -> list[ResolutionAction]:
    """The active shared actions of the workflow's ministry — what a local action may count as."""
    ministry = ministry_of(db, workflow.owner_organization_id) if workflow.owner_organization_id else None
    if not ministry:
        return []
    return list(db.execute(
        select(ResolutionAction).where(
            ResolutionAction.owner_organization_id == ministry,
            ResolutionAction.counts_as_code.is_(None),
            ResolutionAction.is_active.is_(True),
        ).order_by(ResolutionAction.label)
    ).scalars())


def available_actions(db: Session, workflow: WorkflowDefinition, q: Optional[str], limit: int = 20) -> list[ResolutionAction]:
    """Actions the workflow can use and does not already offer — the *Add an action* search."""
    if is_sensitive_workflow(workflow) or not workflow.owner_organization_id:
        return []
    stmt = select(ResolutionAction).where(
        ResolutionAction.is_active.is_(True),
        ResolutionAction.owner_organization_id.in_(ancestor_org_ids(db, workflow.owner_organization_id, include_self=True)),
    )
    on_list = selected_codes(db, workflow.workflow_id, active_only=False)
    if on_list:
        stmt = stmt.where(ResolutionAction.code.notin_(on_list))
    if q and q.strip():
        stmt = stmt.where(func.lower(ResolutionAction.label).like(f"%{q.strip().lower()}%"))
    return list(db.execute(stmt.order_by(ResolutionAction.label).limit(limit)).scalars())


def _new_code(db: Session, label: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", label).strip("_").upper()[:48] or "ACTION"
    while True:
        code = f"{slug}_{uuid.uuid4().hex[:6].upper()}"
        if db.get(ResolutionAction, code) is None:
            return code


def _clean(text: Optional[str], field: str) -> str:
    value = (text or "").strip()
    if not value:
        raise ResolutionCatalogError(f"{field} is required.")
    return value


def create_into_workflow(
    db: Session,
    user: "CurrentUser",
    workflow: WorkflowDefinition,
    *,
    label: str,
    default_wording: str,
    counts_as_code: Optional[str],
    national: bool,
) -> ResolutionAction:
    """Create an action and append it to ``workflow``'s list, in the caller's transaction.

    Every refusal happens **before** the action row is written, so a refused create never leaves an
    unused action in the catalog (actions are never deleted)."""
    if is_sensitive_workflow(workflow):
        raise ResolutionCatalogError("A sensitive workflow does not record a resolution action, so none can be added.")
    if not can_change_list(db, user, workflow):
        raise ResolutionPermissionError("You can only change workflows of organizations you manage.")
    current = selected_codes(db, workflow.workflow_id, active_only=False)
    if len(current) >= MAX_RESOLUTION_ACTIONS:
        raise ResolutionCatalogError(
            f"A workflow can offer at most {MAX_RESOLUTION_ACTIONS} actions. Remove one to add another."
        )
    label = _clean(label, "The action")
    default_wording = _clean(default_wording, "The default text")

    ministry = ministry_of(db, workflow.owner_organization_id)
    if national:
        if not can_create_national(db, user, workflow):
            raise ResolutionPermissionError("Only an admin of the ministry can create a national action.")
        owner, counts_as = ministry, None
    else:
        owner = workflow.owner_organization_id
        counts_as = counts_as_code or None
        if owner == ministry and counts_as:
            raise ResolutionCatalogError("An action of the ministry itself is national and does not count as another.")
        if counts_as:
            _check_counts_as_target(db, counts_as)

    action = create_action(
        db, code=_new_code(db, label), label=label, default_wording=default_wording,
        owner_organization_id=owner, counts_as_code=counts_as, created_by_user_id=user.user_id,
    )
    set_workflow_actions(db, workflow, current + [action.code])
    return action


def _check_counts_as_target(db: Session, code: str) -> None:
    target = db.get(ResolutionAction, code)
    if target is None or not target.is_active:
        raise ResolutionCatalogError(f"{code} is not an active resolution action.")


def update_action(
    db: Session,
    user: "CurrentUser",
    action: ResolutionAction,
    *,
    label: Optional[str] = None,
    default_wording: Optional[str] = None,
    counts_as_code: Optional[str] = None,
    counts_as_set: bool = False,
) -> ResolutionAction:
    """Edit an action's label, default text or what it counts as. ``counts_as_set`` says whether the
    request carried ``counts_as_code`` at all, so an omitted field is not read as "clear it"."""
    if not can_edit_action(db, user, action):
        raise ResolutionPermissionError("You can only edit actions of organizations you manage.")
    if label is not None:
        action.label = _clean(label, "The action")
    if default_wording is not None:
        action.default_wording = _clean(default_wording, "The default text")
    if counts_as_set:
        ministry = ministry_of(db, action.owner_organization_id)
        if ministry == action.owner_organization_id:
            if counts_as_code:
                raise ResolutionCatalogError("A national action does not count as another action.")
        else:
            if not counts_as_code:
                raise ResolutionCatalogError("A local action must say which national action it counts as in national reports.")
            _check_counts_as_target(db, counts_as_code)
            target = db.get(ResolutionAction, counts_as_code)
            if target.owner_organization_id != ministry or target.counts_as_code is not None:
                raise ResolutionCatalogError(f"{counts_as_code} is not a national action of this organization's ministry.")
            action.counts_as_code = counts_as_code
    db.flush()
    return action
