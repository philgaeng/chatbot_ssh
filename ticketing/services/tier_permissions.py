"""
Tier-derived permission resolution (DESIGN-cast-model §3.1, §6 — Option A).

The four WorkflowStep fields ARE the tier cast. A user's tier at a step is derived from
*which field their role_key sits in*; capabilities come from ``TIER_PERMISSIONS`` — never
from ``roles.permissions``. No ``tier`` column, no materialized view: the step fields plus
``officer_scopes.role_key`` remain the single source of truth (§5), and this module is a
pure read over them.

**Enforcement axes (the §7-Phase-1 reconciliation — see followups/tier-permissions-
reconciliation.md).** Holding a tier is necessary but the *gating axis* differs per tier:

  * **Actor** capabilities (acknowledge/escalate/resolve/reply) gate on **assignment
    identity** — the officer the ticket is assigned to — not on merely holding the actor
    role_key. This preserves the historical "only the assignee changes status" rule.
  * **Supervisor** capabilities gate on **tier membership** — holding the step's
    ``supervisor_role`` (== Supervisor tier on that step).
  * **Participant** (note) and **all tiers'** view gate on **ticket visibility** — any
    officer who can see the ticket may note; observers may view.

``capabilities_for_user_on_ticket`` returns the union a user *actually* has, folding those
axes together, so callers get one honest answer to "what can this person do here?"
"""
from __future__ import annotations

from typing import Iterable

from sqlalchemy.orm import Session

from ticketing.constants.tiers import (
    ACTOR,
    OBSERVER,
    PARTICIPANT,
    SUPERVISOR,
    capabilities_for_tier,
    top_tier,
)
from ticketing.engine.workflow_engine import get_current_step
from ticketing.models.ticket import Ticket
from ticketing.models.workflow import WorkflowStep


def step_role_keys_by_tier(step: WorkflowStep) -> dict[str, set[str]]:
    """Map each tier → the set of role_keys the step casts into it."""
    return {
        ACTOR: {step.assigned_role_key} if step.assigned_role_key else set(),
        SUPERVISOR: {step.supervisor_role} if step.supervisor_role else set(),
        PARTICIPANT: set(step.informed_roles or []),
        OBSERVER: set(step.observer_roles or []),
    }


def tiers_held_on_step(step: WorkflowStep, role_keys: Iterable[str]) -> set[str]:
    """Every tier that any of ``role_keys`` occupies on ``step`` (may be >1)."""
    rk = set(role_keys)
    by_tier = step_role_keys_by_tier(step)
    return {tier for tier, keys in by_tier.items() if rk & keys}


def tier_for_role_keys_on_step(step: WorkflowStep, role_keys: Iterable[str]) -> str | None:
    """Highest-precedence tier that ``role_keys`` occupy on ``step`` (§6 precedence)."""
    return top_tier(tiers_held_on_step(step, role_keys))


def user_holds_tier_on_step(step: WorkflowStep, role_keys: Iterable[str], tier: str) -> bool:
    """True when any of ``role_keys`` is cast into ``tier`` on ``step``."""
    return tier in tiers_held_on_step(step, role_keys)


def capabilities_for_user_on_ticket(
    db: Session, ticket: Ticket, current_user
) -> set[str]:
    """The capabilities ``current_user`` actually holds on ``ticket`` at its current step.

    Folds the three enforcement axes (see module docstring). Admins hold every operational
    capability. Callers that need a single gate should prefer this over inspecting tiers
    directly, so the axis rules live in one place.
    """
    if getattr(current_user, "is_admin", False):
        # Admin plane grants all operational ticket capabilities.
        return (
            capabilities_for_tier(ACTOR)
            | capabilities_for_tier(SUPERVISOR)
            | capabilities_for_tier(PARTICIPANT)
            | capabilities_for_tier(OBSERVER)
        )

    step = get_current_step(ticket, db)
    caps: set[str] = set()
    role_keys = getattr(current_user, "role_keys", []) or []

    if step is not None:
        held = tiers_held_on_step(step, role_keys)
        # Supervisor: tier-membership axis.
        if SUPERVISOR in held:
            caps |= capabilities_for_tier(SUPERVISOR)
        # Participant / Observer: visibility axis — a cast participant may note, an
        # observer may view. (Ticket visibility itself is enforced upstream by
        # require_ticket_access; reaching here means the user can see the ticket.)
        if PARTICIPANT in held:
            caps |= capabilities_for_tier(PARTICIPANT)
        if OBSERVER in held:
            caps |= capabilities_for_tier(OBSERVER)

    # Actor: assignment-identity axis — the assigned officer holds the Actor capabilities
    # regardless of which role_key backs the assignment.
    assigned = getattr(ticket, "assigned_to_user_id", None)
    if assigned and current_user.matches_assignee(assigned):
        caps |= capabilities_for_tier(ACTOR)

    return caps
