"""One role key may back only one (step, tier) slot in a workflow.

Philippe, 2026-08-09: *"I cannot save anybody for the ADB HQ Safeguards role on level 3."*

They could — eighteen assignments saved, and every one appeared at **Level 4**, because
`adb_hq_safeguards` was the role key of both L3-supervisor and L4-actor. A cast assignment is
stored in `officer_scopes` as a `role_key` and nothing else: no step, no tier. So two slots
sharing a key are indistinguishable in the data, and `read_cast` — which builds
`role_key -> (step, tier)` — keeps whichever step it saw last.

The display was the *mild* half. Assignment and go-live resolve officers by `role_key`, so
someone added as "kept informed" at Level 3 silently became a candidate **Actor** at Level 4.

Migration `x0z2b4d6` converts existing workflows to synthetic per-slot keys. This pins the guard
that stops the collision being authored again.
"""
from __future__ import annotations

from ticketing.services.cast_staffing import duplicate_slot_keys


class _Step:
    """The four tier fields, which is all `duplicate_slot_keys` reads."""

    def __init__(self, order, actor=None, supervisor=None, informed=None, observer=None):
        self.step_order = order
        self.assigned_role_key = actor
        self.supervisor_role = supervisor
        self.informed_roles = informed or []
        self.observer_roles = observer or []


def test_distinct_keys_are_fine():
    steps = [
        _Step(1, actor="wf:X:L1:actor", supervisor="wf:X:L1:supervisor"),
        _Step(2, actor="wf:X:L2:actor", supervisor="wf:X:L2:supervisor"),
    ]
    assert duplicate_slot_keys(steps) == {}


def test_the_ladder_collision_is_caught():
    """The real shape: level N's supervisor named with level N+1's actor role."""
    steps = [
        _Step(3, actor="grc_chair", supervisor="adb_hq_safeguards"),
        _Step(4, actor="adb_hq_safeguards"),
    ]
    dupes = duplicate_slot_keys(steps)
    assert set(dupes) == {"adb_hq_safeguards"}
    assert dupes["adb_hq_safeguards"] == ["L3/supervisor", "L4/actor"]


def test_a_key_repeated_across_four_slots_reports_all_of_them():
    """`dor_dpd_adb` really did this — observer twice, then supervisor, then actor."""
    steps = [
        _Step(1, actor="a", observer=["dor_dpd_adb"]),
        _Step(2, actor="b", observer=["dor_dpd_adb"]),
        _Step(3, actor="c", supervisor="dor_dpd_adb"),
        _Step(4, actor="dor_dpd_adb"),
    ]
    assert len(duplicate_slot_keys(steps)["dor_dpd_adb"]) == 4


def test_list_tiers_are_read_member_by_member():
    """Informed and observer are JSON lists; a key hiding in one still collides."""
    steps = [
        _Step(1, actor="a", informed=["x", "shared"]),
        _Step(2, actor="b", observer=["shared"]),
    ]
    assert set(duplicate_slot_keys(steps)) == {"shared"}


def test_the_same_key_on_two_tiers_of_one_step_collides_too():
    """Actor and supervisor of one step is also the self-escalation case (§3.3) — but this
    catches it structurally, before anyone is assigned."""
    steps = [_Step(1, actor="same", supervisor="same")]
    assert set(duplicate_slot_keys(steps)) == {"same"}


def test_empty_tiers_are_not_a_collision():
    """Every step leaves supervisor/informed/observer empty — `None` and `[]` are not keys."""
    steps = [_Step(1, actor="a"), _Step(2, actor="b")]
    assert duplicate_slot_keys(steps) == {}
