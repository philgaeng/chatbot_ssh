# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""Give every job at every level the name it is already showing.

The workflow author names each job at a level — "Safeguard Officer", "Escalation Lead" —
and those names are what officers read on every screen (doc 12 §6.2, doc 13 §5A.1). The
model (`workflow_steps.tier_labels`) and the editor both exist. What was missing is that
**nothing was ever authored**: every seeded workflow has `tier_labels = {}`, so every screen
fell through to a second-choice display — the name of the *role* bound to the job
("Site Safeguards Focal Person"). It looked, correctly, as though the workflow screen were
being ignored.

This writes what each screen currently displays into the workflow itself, so the words become
**owned** rather than borrowed. Nothing changes visually; the same string simply now comes from
the workflow. That is what lets the role-name fallback be deleted in the same change — with no
fallback and no blanks, the workflow screen is provably the only source of a job's name.

Only fills what is empty:
  • a tier that is not enabled on the step is skipped (no supervisor bound ⇒ no supervisor name);
  • a tier the author already named is left alone;
  • a tier with no bound role and no name stays blank — there is nothing true to write, and the
    new save-time validation asks the author for it.

Revision ID: r4t6v8x0
Revises: p2r4t6v8
Create Date: 2026-08-04
"""
from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "r4t6v8x0"
down_revision: Union[str, None] = "p2r4t6v8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _as_dict(value) -> dict:
    if not value:
        return {}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return {}
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value) -> list:
    if not value:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return []
    return list(value) if isinstance(value, list) else []


def upgrade() -> None:
    conn = op.get_bind()

    roles = {
        r["role_key"]: r["display_name"]
        for r in conn.execute(
            sa.text("SELECT role_key, display_name FROM ticketing.roles")
        ).mappings()
    }

    steps = conn.execute(sa.text("""
        SELECT step_id, assigned_role_key, supervisor_role, informed_roles, observer_roles,
               tier_labels
          FROM ticketing.workflow_steps
         WHERE is_deleted = false
    """)).mappings().all()

    for s in steps:
        labels = _as_dict(s["tier_labels"])
        bound = {
            "actor": s["assigned_role_key"] or None,
            "supervisor": s["supervisor_role"] or None,
            "participant": (_as_list(s["informed_roles"]) or [None])[0],
            "observer": (_as_list(s["observer_roles"]) or [None])[0],
        }
        changed = False
        for tier, role_key in bound.items():
            if not role_key:
                continue  # tier not enabled on this step
            entry = labels.get(tier) or {}
            if (entry.get("label") or "").strip():
                continue  # the author already named it
            name = roles.get(role_key)
            if not name:
                # A synthetic per-step key with no catalog row has no name to inherit; leave it
                # blank so the author is asked rather than shown an invented word.
                continue
            entry["label"] = name
            labels[tier] = entry
            changed = True

        if changed:
            conn.execute(
                sa.text("""
                    UPDATE ticketing.workflow_steps
                       SET tier_labels = CAST(:labels AS json)
                     WHERE step_id = :step_id
                """),
                {"labels": json.dumps(labels), "step_id": s["step_id"]},
            )


def downgrade() -> None:
    """Not reversible in a meaningful way: an authored name and a back-filled one are the same
    shape, so removing "the ones this migration wrote" would also remove any the author has
    edited since. Leaving the names in place is harmless — they are only labels."""
