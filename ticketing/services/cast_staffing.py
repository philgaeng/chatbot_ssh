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
