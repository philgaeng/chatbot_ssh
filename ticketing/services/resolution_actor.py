# SPDX-License-Identifier: Apache-2.0

"""Who took the action that resolved a case — the *Resolved by* of the manager's Excel (GRM-117).

Three answers, **none of them typed** (DESIGN §3.2): the resolving officer's own **office**, another
organization from the directory, or one of a fixed list of outside bodies. The whole point is that the
column cannot hold a person's name, so the label is always computed here from an organization row or
the fixed list — a request cannot set it.

**A case in a sensitive workflow records no actor** (DESIGN §3.1.3): *Resolved by: Police* on a SEAH
row re-identifies as surely as an action label.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ticketing.constants.resolution import RESOLUTION_EXTERNAL_ACTORS
from ticketing.models.officer_position import OfficerPosition
from ticketing.models.organization import Organization
from ticketing.models.package import PackageOrganization
from ticketing.models.project import ProjectOrganization
from ticketing.models.ticket import Ticket
from ticketing.models.workflow import WorkflowDefinition
from ticketing.services.org_tree import descendant_org_ids
from ticketing.services.resolution_catalog import is_sensitive_workflow

ACTOR_KINDS = ("self", "organization", "external")
_EXTERNAL_LABELS = dict(RESOLUTION_EXTERNAL_ACTORS)


class ResolutionActorError(ValueError):
    """An actor the rules refuse. The officer-action engine maps it to a 422."""


@dataclass(frozen=True)
class ResolvedActor:
    kind: str
    organization_id: Optional[str]
    external: Optional[str]
    label: str

    def payload(self) -> dict:
        return {
            "resolution_actor_kind": self.kind,
            "resolution_actor_organization_id": self.organization_id,
            "resolution_actor_external": self.external,
            "resolution_actor_label": self.label,
        }


def records_actor(db: Session, ticket: Ticket) -> bool:
    """False for a case in a sensitive workflow — it records no actor."""
    workflow = db.get(WorkflowDefinition, ticket.current_workflow_id) if ticket.current_workflow_id else None
    if workflow is not None:
        return not is_sensitive_workflow(workflow)
    return not ticket.is_seah


def _org_rows(db: Session, ids: set[str], *, active_only: bool = False) -> list[Organization]:
    if not ids:
        return []
    stmt = select(Organization).where(Organization.organization_id.in_(ids))
    if active_only:
        stmt = stmt.where(Organization.is_active.is_(True))
    return list(db.execute(stmt.order_by(Organization.name)).scalars())


def _linked_org_ids(db: Session, ticket: Ticket) -> set[str]:
    """Organizations named on the case's project, and on its package when it has one."""
    ids: set[str] = set()
    if ticket.project_id:
        ids |= set(db.execute(
            select(ProjectOrganization.organization_id).where(ProjectOrganization.project_id == ticket.project_id)
        ).scalars())
    if ticket.package_id:
        ids |= set(db.execute(
            select(PackageOrganization.organization_id).where(PackageOrganization.package_id == ticket.package_id)
        ).scalars())
    return ids


def resolve_self_offices(db: Session, user_id: str, ticket: Ticket) -> list[dict]:
    """"My office" for this case (DESIGN §3.2.1) — one entry when it is decided, several when the
    officer must choose among their own offices:

    1. one active position → its organization;
    2. several → those whose organization is linked to the case's project or package, **or is above a
       linked one**; if that leaves exactly one, it; otherwise the officer chooses (among the linked
       ones if any, else among all);
    3. no active position → the case's own organization.
    """
    position_orgs = set(db.execute(
        select(OfficerPosition.organization_id).where(
            OfficerPosition.user_id == user_id, OfficerPosition.is_active.is_(True)
        )
    ).scalars())
    if not position_orgs:
        fallback = _org_rows(db, {ticket.organization_id}) if ticket.organization_id else []
        if fallback:
            return [{"organization_id": fallback[0].organization_id, "name": fallback[0].name}]
        return [{"organization_id": ticket.organization_id, "name": ticket.organization_id}] if ticket.organization_id else []

    candidates = position_orgs
    if len(position_orgs) > 1:
        linked = _linked_org_ids(db, ticket)
        on_case = {o for o in position_orgs if descendant_org_ids(db, o, include_self=True) & linked}
        if on_case:
            candidates = on_case
    return [{"organization_id": o.organization_id, "name": o.name} for o in _org_rows(db, candidates)]


def office_suggestions(db: Session, ticket: Ticket) -> list[dict]:
    """The organizations linked to the case's project and package — the office that acted is almost
    always one of them, so the form lists them before the officer searches."""
    return [{"organization_id": o.organization_id, "name": o.name}
            for o in _org_rows(db, _linked_org_ids(db, ticket), active_only=True)]


def external_actor_choices() -> list[dict]:
    return [{"key": key, "label": label} for key, label in RESOLUTION_EXTERNAL_ACTORS]


def resolve_actor(
    db: Session,
    ticket: Ticket,
    user_id: str,
    *,
    kind: Optional[str],
    organization_id: Optional[str],
    external: Optional[str],
) -> Optional[ResolvedActor]:
    """Validate the requested actor and compute its label. None for a case that records no actor.
    Raises :class:`ResolutionActorError` naming the field."""
    if not records_actor(db, ticket):
        if kind or organization_id or external:
            raise ResolutionActorError(
                "This case's workflow does not record who took the action. Send the resolution text only."
            )
        return None

    kind = kind or "self"
    if kind not in ACTOR_KINDS:
        raise ResolutionActorError("resolution_actor_kind must be one of: self, organization, external.")

    if kind == "external":
        if external not in _EXTERNAL_LABELS:
            raise ResolutionActorError("resolution_actor_external must be one of the listed outside bodies.")
        return ResolvedActor("external", None, external, _EXTERNAL_LABELS[external])

    if kind == "organization":
        if not organization_id:
            raise ResolutionActorError("resolution_actor_organization_id is required — choose the office that took the action.")
        org = db.get(Organization, organization_id)
        if org is None or not org.is_active:
            raise ResolutionActorError("resolution_actor_organization_id is not an active organization.")
        return ResolvedActor("organization", org.organization_id, None, org.name)

    offices = resolve_self_offices(db, user_id, ticket)
    if not offices:
        raise ResolutionActorError("Your office could not be determined — choose 'Another office'.")
    if organization_id:
        match = next((o for o in offices if o["organization_id"] == organization_id), None)
        if match is None:
            raise ResolutionActorError("resolution_actor_organization_id is not one of your offices.")
    elif len(offices) == 1:
        match = offices[0]
    else:
        raise ResolutionActorError("resolution_actor_organization_id is required — choose which of your offices took the action.")
    return ResolvedActor("self", match["organization_id"], None, match["name"])
