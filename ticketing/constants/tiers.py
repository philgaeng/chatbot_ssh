"""
Cast tiers — the fixed, extensible participation model (DESIGN-cast-model §3.1, §6).

The four WorkflowStep role fields ARE the tier cast; this module names them and pins
the tier → capability map. Permissions are now **tier-derived**, not per-role: a person's
capabilities come from *which step field their role_key sits in*, never from
``roles.permissions`` (which is invisible plumbing, read only during the transition).

Extending the model later = append a tier here + a permissions migration/seed. There is
no user-facing catalogue, no per-role permission editor, and no admin-leak guard on this
plane — operational capabilities are fixed by tier, and admin caps live only on the admin
plane (`admin_scopes`).

Two capabilities are deliberately **not** tiers (see §3.1):
  * GRC convene/decide — a per-step capability of the Actor at the GRC step (Phase 5 flag).
  * SEAH access — a workflow-*track* property, not a role/tier (Phase 5 re-key).

Reassignment is modelled as the ``can_reassign`` capability (Phase 4), granted to the
Supervisor by default (+ optional per-step Actor self-serve + a staffed Dispatcher), so it
is listed in the Supervisor tier's capabilities but ultimately resolved by the §3.4 chain.
"""
from __future__ import annotations

# ── The four fixed tiers ────────────────────────────────────────────────────
ACTOR = "actor"            # owns & works the case at a step  (WorkflowStep.assigned_role_key)
SUPERVISOR = "supervisor"  # oversees; escalation/reassign target (WorkflowStep.supervisor_role)
PARTICIPANT = "participant"  # informed + can note (WorkflowStep.informed_roles[])
OBSERVER = "observer"      # informed, read-only (WorkflowStep.observer_roles[])

# Ordered; extensible by appending (+ seed perms). Do not reorder — precedence below.
TIERS: list[str] = [ACTOR, SUPERVISOR, PARTICIPANT, OBSERVER]

# Which WorkflowStep field holds each tier's role_key(s).
# actor/supervisor are scalar columns; participant/observer are JSON lists.
STEP_FIELD_BY_TIER: dict[str, str] = {
    ACTOR: "assigned_role_key",
    SUPERVISOR: "supervisor_role",
    PARTICIPANT: "informed_roles",
    OBSERVER: "observer_roles",
}
_SCALAR_TIER_FIELDS = {ACTOR, SUPERVISOR}  # scalar String columns (vs JSON list columns)

# Precedence when a user matches >1 field on a step (§6): Actor > Supervisor > Participant
# > Observer. The §3.3 self-escalation guard already prevents the Actor+Supervisor overlap.
TIER_PRECEDENCE: list[str] = [ACTOR, SUPERVISOR, PARTICIPANT, OBSERVER]

# ── Tier → capability map (§9 permissions matrix) ───────────────────────────
# These capability strings are the operational vocabulary the runtime already gates on
# (see docs/.../DESIGN-cast-model §9 and the tier-permissions reconciliation note for
# which axis actually enforces each one: Actor caps gate on assignment identity,
# Supervisor caps on tier membership, Participant/Observer on ticket visibility).
VIEW = "tickets:read"
NOTE = "tickets:note"
ACKNOWLEDGE = "tickets:acknowledge"
ESCALATE = "tickets:escalate"
RESOLVE = "tickets:resolve"
REPLY = "tickets:reply"
REASSIGN = "tickets:reassign"

TIER_PERMISSIONS: dict[str, list[str]] = {
    ACTOR: [VIEW, NOTE, ACKNOWLEDGE, ESCALATE, RESOLVE, REPLY],
    SUPERVISOR: [VIEW, NOTE, ACKNOWLEDGE, ESCALATE, RESOLVE, REPLY, REASSIGN],
    PARTICIPANT: [VIEW, NOTE],
    OBSERVER: [VIEW],
}


def top_tier(tiers: set[str] | frozenset[str]) -> str | None:
    """Highest-precedence tier in ``tiers`` (Actor > Supervisor > Participant > Observer)."""
    for tier in TIER_PRECEDENCE:
        if tier in tiers:
            return tier
    return None


def capabilities_for_tier(tier: str | None) -> set[str]:
    """The capability set granted by ``tier`` (empty for an unknown/None tier)."""
    return set(TIER_PERMISSIONS.get(tier or "", ()))
