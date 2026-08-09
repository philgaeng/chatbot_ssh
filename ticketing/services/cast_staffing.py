"""
Per-package cast staffing (DESIGN-cast-model §3.3, §3.6, §6).

Turns "who plays which tier, per package" into ``officer_scopes`` — the enforcement rows —
through the sanctioned writers only (``create_scope_row``). No new enforcement path: the
generated scopes flow through the same ``_scope_candidates`` auto-assign as always (§5).

**Synthetic per-step-tier role_key.** A simplified workflow step no longer names roles; each
enabled tier slot carries an opaque, system-managed key ``wf:{workflow_key}:{step_key}:{tier}``
so pools stay separate per step (§6). Each such key is backed by a system ``roles`` row — the
"invisible plumbing" the UI never shows. Existing *named* keys coexist and are never renamed;
only newly-enabled slots mint synthetic keys.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ticketing.constants.tiers import (
    ACTOR,
    OBSERVER,
    PARTICIPANT,
    STEP_FIELD_BY_TIER,
    SUPERVISOR,
    TIERS,
)
from ticketing.models.officer_scope import OfficerScope
from ticketing.models.user import Role
from ticketing.models.workflow import WorkflowDefinition, WorkflowStep

SYNTHETIC_PREFIX = "wf"

_TIER_LABEL = {
    ACTOR: "Actor",
    SUPERVISOR: "Supervisor",
    PARTICIPANT: "Participant",
    OBSERVER: "Observer",
}


def step_tier_role_key(workflow_key: str, step_key: str, tier: str) -> str:
    """The opaque per-step-tier key. Format: ``wf:{workflow_key}:{step_key}:{tier}``."""
    return f"{SYNTHETIC_PREFIX}:{workflow_key}:{step_key}:{tier}"


def is_synthetic_key(role_key: str | None) -> bool:
    return bool(role_key) and role_key.startswith(SYNTHETIC_PREFIX + ":")


def parse_synthetic_key(role_key: str | None) -> tuple[str, str, str] | None:
    """(workflow_key, step_key, tier) for a synthetic key, else None."""
    if not is_synthetic_key(role_key):
        return None
    parts = role_key.split(":")
    if len(parts) != 4:
        return None
    _, workflow_key, step_key, tier = parts
    return (workflow_key, step_key, tier) if tier in TIERS else None


def workflow_scope_for_track(workflow_type: str | None) -> str:
    """Role.workflow_scope value for a workflow's track."""
    return "SEAH" if (workflow_type or "").lower() == "seah" else "Standard"


def ensure_tier_role(
    db: Session, *, role_key: str, tier: str, workflow: WorkflowDefinition, step_name: str
) -> Role:
    """Ensure the system ``roles`` row backing a synthetic key exists (idempotent).

    These rows are plumbing: ``role_origin='system'``, ``role_kind='operational'``,
    ``permissions=[]`` (permissions are tier-derived now), scope from the workflow track.
    """
    role = db.execute(select(Role).where(Role.role_key == role_key)).scalar_one_or_none()
    if role is not None:
        return role
    role = Role(
        role_key=role_key,
        display_name=f"{_TIER_LABEL.get(tier, tier.title())} — {step_name}",
        description="System tier-holder (cast model plumbing — not user-editable).",
        workflow_scope=workflow_scope_for_track(workflow.workflow_type),
        jurisdiction_mode="field",
        permissions=[],
        role_kind="operational",
        role_origin="system",
        archetype=None,
    )
    db.add(role)
    db.flush()
    return role


def set_step_tier_keys(
    db: Session,
    workflow: WorkflowDefinition,
    step: WorkflowStep,
    *,
    supervisor: bool,
    participants: bool,
    observers: bool,
) -> None:
    """Set a step's four tier fields from on/off toggles (DESIGN-cast-model §3.5).

    Actor is always on. For each enabled tier whose field is empty, mint the synthetic key
    (+ backing role); a field already holding a (named or synthetic) key is kept — existing
    keys coexist, only newly-enabled slots mint. A disabled tier is cleared.
    """
    wf_key = workflow.workflow_key
    name = step.display_name or step.step_key

    # Actor — always on.
    if not step.assigned_role_key:
        key = step_tier_role_key(wf_key, step.step_key, ACTOR)
        ensure_tier_role(db, role_key=key, tier=ACTOR, workflow=workflow, step_name=name)
        step.assigned_role_key = key

    # Supervisor — scalar field.
    if supervisor:
        if not step.supervisor_role:
            key = step_tier_role_key(wf_key, step.step_key, SUPERVISOR)
            ensure_tier_role(db, role_key=key, tier=SUPERVISOR, workflow=workflow, step_name=name)
            step.supervisor_role = key
    else:
        step.supervisor_role = None

    # Participant / Observer — JSON-list fields; the step's synthetic key is the sole member.
    for tier, enabled in ((PARTICIPANT, participants), (OBSERVER, observers)):
        field = STEP_FIELD_BY_TIER[tier]
        current = list(getattr(step, field) or [])
        if enabled:
            if not current:
                key = step_tier_role_key(wf_key, step.step_key, tier)
                ensure_tier_role(db, role_key=key, tier=tier, workflow=workflow, step_name=name)
                setattr(step, field, [key])
            # else: keep existing (named or synthetic) members
        else:
            setattr(step, field, [])


def self_escalation_conflict(
    db: Session,
    *,
    workflow_key: str,
    step_key: str,
    tier: str,
    user_id: str,
    package_id: str | None,
    project_id: str | None,
) -> bool:
    """True if staffing ``user_id`` into this (step, tier) would make them **both** Actor and
    Supervisor of the same step in the same package (§3.3 self-escalation guard).

    Only meaningful for synthetic per-step-tier keys, where the sibling tier's key is derivable.
    """
    if tier not in (ACTOR, SUPERVISOR):
        return False
    sibling = SUPERVISOR if tier == ACTOR else ACTOR
    sibling_key = step_tier_role_key(workflow_key, step_key, sibling)
    stmt = select(OfficerScope.scope_id).where(
        OfficerScope.user_id == user_id,
        OfficerScope.role_key == sibling_key,
    )
    # Same package (or same project-wide slot when no package).
    if package_id:
        stmt = stmt.where(OfficerScope.package_id == package_id)
    else:
        stmt = stmt.where(
            OfficerScope.package_id.is_(None),
            OfficerScope.project_id == project_id,
        )
    return db.execute(stmt.limit(1)).first() is not None


def duplicate_slot_keys(steps) -> dict[str, list[str]]:
    """Role keys that back more than one (step, tier) slot in one workflow.

    **Why this cannot be allowed** (2026-08-09). A cast assignment is stored in
    ``officer_scopes`` as a ``role_key`` and nothing else — no step, no tier. So two slots
    sharing a key are indistinguishable *in the data*, and everything downstream picks one:

      * ``read_cast`` builds ``role_key -> (step, tier)`` and the last step processed wins, so
        officers staffed into the earlier slot render against the later one. On staging,
        ``adb_hq_safeguards`` backed both L3-supervisor and L4-actor, and 18 assignments made at
        Level 3 all appeared at Level 4 — the author concluded, reasonably, that Level 3 could
        not be staffed at all.
      * Worse than display: go-live and assignment resolve officers by ``role_key``, so anyone
        added as "kept informed" at L3 silently became a candidate **Actor** at L4.

    Synthetic per-slot keys (``step_tier_role_key``) are unique by construction and are what
    ``set_step_tier_keys`` mints — but only into *empty* fields, so workflows seeded with named
    operational roles kept theirs and collided. This makes the collision unpublishable rather
    than merely repaired once.

    Returns ``{role_key: ["L3/supervisor", "L4/actor"]}`` for the offenders only.
    """
    from collections import defaultdict

    seen: dict[str, list[str]] = defaultdict(list)
    for step in steps:
        for tier in (ACTOR, SUPERVISOR, PARTICIPANT, OBSERVER):
            field = STEP_FIELD_BY_TIER[tier]
            value = getattr(step, field, None)
            keys = value if isinstance(value, list) else [value]
            for key in keys:
                if key:
                    seen[key].append(f"L{step.step_order}/{tier}")
    return {k: v for k, v in seen.items() if len(v) > 1}
