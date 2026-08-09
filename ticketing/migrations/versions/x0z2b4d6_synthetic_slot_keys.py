# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
"""Every (step, tier) slot gets its own role key.

Philippe, 2026-08-09: *"I cannot save anybody for the ADB HQ Safeguards role on level 3."*

They could. Eighteen assignments saved — and every one of them appeared at **Level 4**, because
`adb_hq_safeguards` was the role key of *both* L3-supervisor and L4-actor. A cast assignment is
stored in `officer_scopes` as a `role_key` and nothing else: no step, no tier. Two slots sharing
a key are therefore indistinguishable in the data, and:

  * `read_cast` builds `role_key -> (step, tier)`, so the last step processed wins and the
    earlier slot's officers render against the later one;
  * assignment and go-live resolve officers **by role_key**, so someone added as "kept informed"
    at L3 silently became a candidate **Actor** at L4. That is a permission fault, not a
    display one.

The collision was systemic, not accidental: this ladder names level N's supervisor and level
N+1's actor with the same operational role. Five keys collided, one of them (`dor_dpd_adb`)
across **four** slots.

Synthetic per-slot keys (`wf:{workflow_key}:{step_key}:{tier}`) are unique by construction and
are what `set_step_tier_keys` already mints — but only into *empty* fields, so workflows seeded
with named operational roles kept theirs. This converts them.

**Existing assignments.** A scope row carries only the old key, so it can be re-pointed only
when that key backed exactly **one** slot. Those are remapped. Where the key backed several,
which slot a row meant is genuinely unknowable — and guessing could promote an observer into an
actor, so those rows are **left alone**. They become inert: no slot uses their key any more, so
they grant nothing in these workflows, and the officers simply need re-assigning on a screen
that can now tell the slots apart. `docs/sprints/followups/` records them.

Revision ID: x0z2b4d6
Revises: v8x0z2b4
Create Date: 2026-08-09
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "x0z2b4d6"
down_revision: Union[str, None] = "v8x0z2b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SYNTHETIC_PREFIX = "wf"
ROLE_KEY_MAX = 64

# (tier, step column, is the column a JSON list?)
TIER_FIELDS = (
    ("actor", "assigned_role_key", False),
    ("supervisor", "supervisor_role", False),
    ("informed", "informed_roles", True),
    ("observer", "observer_roles", True),
)
TIER_LABEL = {
    "actor": "Actor",
    "supervisor": "Supervisor",
    "informed": "Kept informed",
    "observer": "Observer",
}


def _synthetic(workflow_key: str, step_key: str, tier: str) -> str:
    return f"{SYNTHETIC_PREFIX}:{workflow_key}:{step_key}:{tier}"


def upgrade() -> None:
    bind = op.get_bind()

    steps = bind.execute(
        sa.text(
            """
            SELECT s.step_id, s.step_order, s.step_key, s.display_name,
                   s.assigned_role_key, s.supervisor_role, s.informed_roles, s.observer_roles,
                   w.workflow_id, w.workflow_key, w.workflow_type
            FROM ticketing.workflow_steps s
            JOIN ticketing.workflow_definitions w ON w.workflow_id = s.workflow_id
            WHERE s.is_deleted IS NOT TRUE
            ORDER BY w.workflow_key, s.step_order
            """
        )
    ).mappings().all()

    # Pass 1 — every named key, and the slots it backs. Only keys backing exactly one slot can
    # have their assignments carried across.
    slots_by_key: dict[str, list[tuple]] = defaultdict(list)
    for row in steps:
        for tier, column, is_list in TIER_FIELDS:
            value = row[column]
            keys = (value or []) if is_list else ([value] if value else [])
            for key in keys:
                if key and not str(key).startswith(SYNTHETIC_PREFIX + ":"):
                    slots_by_key[key].append((row, tier, column, is_list))

    # Pass 2 — mint the backing role and re-point the step field, slot by slot.
    for key, slots in slots_by_key.items():
        for row, tier, column, is_list in slots:
            new_key = _synthetic(row["workflow_key"], row["step_key"], tier)
            if len(new_key) > ROLE_KEY_MAX:
                raise RuntimeError(
                    f"Synthetic key '{new_key}' exceeds {ROLE_KEY_MAX} characters — shorten the "
                    f"workflow key or step key for workflow {row['workflow_key']} first."
                )
            scope = "seah" if (row["workflow_type"] or "").lower() == "seah" else "standard"
            bind.execute(
                sa.text(
                    """
                    -- created_at/updated_at are NOT NULL with Python-side defaults, so a raw
                    -- INSERT has to supply them.
                    INSERT INTO ticketing.roles
                        (role_id, role_key, display_name, description, workflow_scope,
                         jurisdiction_mode, permissions, role_kind, role_origin,
                         created_at, updated_at)
                    VALUES
                        (:rid, :rkey, :dname, :descr, :scope, 'field', '[]', 'operational',
                         'system', now(), now())
                    ON CONFLICT (role_key) DO NOTHING
                    """
                ),
                {
                    "rid": str(uuid.uuid4()),
                    "rkey": new_key,
                    "dname": f"{TIER_LABEL[tier]} — {row['display_name'] or row['step_key']}",
                    "descr": "System tier-holder (cast model plumbing — not user-editable).",
                    "scope": scope,
                },
            )
            if is_list:
                # The step's own key is the sole member, matching set_step_tier_keys.
                # Explicit cast: the column is `json`, and a bound parameter arrives as text.
                bind.execute(
                    sa.text(
                        f"UPDATE ticketing.workflow_steps SET {column} = CAST(:val AS json) "  # noqa: S608 - column from a fixed tuple
                        "WHERE step_id = :sid"
                    ),
                    {"val": f'["{new_key}"]', "sid": row["step_id"]},
                )
            else:
                bind.execute(
                    sa.text(
                        f"UPDATE ticketing.workflow_steps SET {column} = :val "  # noqa: S608 - column from a fixed tuple
                        "WHERE step_id = :sid"
                    ),
                    {"val": new_key, "sid": row["step_id"]},
                )

    # Pass 3 — carry the assignments across, wherever the destination is not a guess.
    #
    # Ambiguity is **per workflow**, not global. One operational role legitimately appears in
    # several workflows (`site_safeguards_focal_person` is Level 1's actor in more than one),
    # and a scope row names the project it belongs to — so it can be attributed to the workflow
    # that project actually binds. Only a key backing two slots *within the same workflow* is
    # genuinely unattributable, which is the collision this migration exists to remove.
    for key, slots in slots_by_key.items():
        # Backed exactly one slot anywhere: every scope carrying it means that slot, including
        # the ones with no project_id (country-wide fallbacks), which no attribution by project
        # could reach.
        if len(slots) == 1:
            row, tier, _c, _l = slots[0]
            bind.execute(
                sa.text(
                    "UPDATE ticketing.officer_scopes SET role_key = :new WHERE role_key = :old"
                ),
                {"new": _synthetic(row["workflow_key"], row["step_key"], tier), "old": key},
            )
            continue

        per_workflow: dict[str, list[tuple]] = defaultdict(list)
        for row, tier, column, is_list in slots:
            per_workflow[row["workflow_id"]].append((row, tier))
        for workflow_id, wf_slots in per_workflow.items():
            if len(wf_slots) != 1:
                continue  # two slots, one key, same workflow — the guess this refuses to make
            row, tier = wf_slots[0]
            bind.execute(
                sa.text(
                    """
                    UPDATE ticketing.officer_scopes SET role_key = :new
                    WHERE role_key = :old
                      AND project_id IN (
                            SELECT project_id FROM ticketing.project_workflows
                            WHERE workflow_id = :wid
                            UNION
                            SELECT project_id FROM ticketing.projects
                            WHERE standard_workflow_id = :wid OR seah_workflow_id = :wid
                      )
                    """
                ),
                {
                    "new": _synthetic(row["workflow_key"], row["step_key"], tier),
                    "old": key,
                    "wid": workflow_id,
                },
            )


def downgrade() -> None:
    # Not reversible: the named key a slot used to hold is not recorded anywhere once replaced,
    # and re-deriving it would have to invent the very collisions this removed.
    raise NotImplementedError(
        "x0z2b4d6 cannot be reversed — restore from backup if a rollback is needed."
    )
