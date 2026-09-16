"""Tier-derived permission resolution (DESIGN-cast-model §3.1, §6 — Phase 1).

Pure unit tests (no DB): the four WorkflowStep fields are the tier cast; a user's tier is
derived from which field their role_key sits in, and capabilities come from TIER_PERMISSIONS.
Also pins the §7-Phase-1 reconciliation folded into ``capabilities_for_user_on_ticket``:
Actor caps gate on assignment identity, Supervisor on tier membership, Participant/Observer
on visibility.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from ticketing.constants.tiers import (
    ACTOR,
    OBSERVER,
    PARTICIPANT,
    SUPERVISOR,
    TIER_PERMISSIONS,
    TIERS,
    capabilities_for_tier,
    top_tier,
)
from ticketing.services.tier_permissions import (
    capabilities_for_user_on_ticket,
    step_role_keys_by_tier,
    tier_for_role_keys_on_step,
    tiers_held_on_step,
    user_holds_tier_on_step,
)


def _step(**kw):
    """A duck-typed WorkflowStep with just the four tier fields."""
    return SimpleNamespace(
        assigned_role_key=kw.get("assigned_role_key", "actor_role"),
        supervisor_role=kw.get("supervisor_role"),
        informed_roles=kw.get("informed_roles", []),
        observer_roles=kw.get("observer_roles", []),
    )


# --- the fixed model ---------------------------------------------------------

def test_tiers_are_the_four_fixed_tiers():
    assert TIERS == [ACTOR, SUPERVISOR, PARTICIPANT, OBSERVER]


def test_tier_permissions_matrix_matches_spec_section_9():
    # view everywhere; note for actor/supervisor/participant; ack/escalate/resolve/reply
    # for actor+supervisor; reassign (can_reassign) listed on supervisor.
    assert TIER_PERMISSIONS[OBSERVER] == ["tickets:read"]
    assert set(TIER_PERMISSIONS[PARTICIPANT]) == {"tickets:read", "tickets:note"}
    for cap in ("tickets:acknowledge", "tickets:escalate", "tickets:resolve", "tickets:reply"):
        assert cap in TIER_PERMISSIONS[ACTOR]
        assert cap in TIER_PERMISSIONS[SUPERVISOR]
    assert "tickets:reassign" in TIER_PERMISSIONS[SUPERVISOR]
    assert "tickets:reassign" not in TIER_PERMISSIONS[ACTOR]  # actor reassign is a per-step toggle
    # participant/observer never get workflow actions
    for tier in (PARTICIPANT, OBSERVER):
        for cap in ("tickets:acknowledge", "tickets:escalate", "tickets:resolve"):
            assert cap not in TIER_PERMISSIONS[tier]


@pytest.mark.parametrize(
    "tiers,expected",
    [
        ({ACTOR, SUPERVISOR}, ACTOR),
        ({SUPERVISOR, PARTICIPANT}, SUPERVISOR),
        ({PARTICIPANT, OBSERVER}, PARTICIPANT),
        ({OBSERVER}, OBSERVER),
        (set(), None),
    ],
)
def test_top_tier_precedence(tiers, expected):
    assert top_tier(tiers) == expected


# --- derivation from a step --------------------------------------------------

def test_step_role_keys_by_tier_maps_each_field():
    step = _step(
        assigned_role_key="a", supervisor_role="s",
        informed_roles=["p1", "p2"], observer_roles=["o"],
    )
    by_tier = step_role_keys_by_tier(step)
    assert by_tier[ACTOR] == {"a"}
    assert by_tier[SUPERVISOR] == {"s"}
    assert by_tier[PARTICIPANT] == {"p1", "p2"}
    assert by_tier[OBSERVER] == {"o"}


def test_empty_scalar_fields_yield_no_keys():
    step = _step(assigned_role_key="", supervisor_role=None, informed_roles=[], observer_roles=[])
    by_tier = step_role_keys_by_tier(step)
    assert by_tier[ACTOR] == set()
    assert by_tier[SUPERVISOR] == set()


def test_tiers_held_and_precedence():
    step = _step(assigned_role_key="a", supervisor_role="s", informed_roles=["p"], observer_roles=["o"])
    assert tiers_held_on_step(step, ["s"]) == {SUPERVISOR}
    assert tier_for_role_keys_on_step(step, ["s"]) == SUPERVISOR
    # a user cast into two tiers gets the highest by precedence
    assert tier_for_role_keys_on_step(step, ["a", "o"]) == ACTOR
    assert tier_for_role_keys_on_step(step, ["unknown"]) is None
    assert user_holds_tier_on_step(step, ["p"], PARTICIPANT) is True
    assert user_holds_tier_on_step(step, ["p"], OBSERVER) is False


def test_capabilities_for_tier():
    assert capabilities_for_tier(OBSERVER) == {"tickets:read"}
    assert capabilities_for_tier(None) == set()
    assert "tickets:resolve" in capabilities_for_tier(ACTOR)


# --- folded resolver: the three enforcement axes -----------------------------

class _FakeDB:
    def __init__(self, step):
        self._step = step

    def get(self, _model, _id):
        return self._step


def _user(role_keys, uid="u1", is_admin=False):
    return SimpleNamespace(
        is_admin=is_admin,
        role_keys=role_keys,
        user_id=uid,
        matches_assignee=lambda a, _uid=uid: a == _uid,
    )


def _ticket(step_id="step1", assigned=None):
    return SimpleNamespace(current_step_id=step_id, assigned_to_user_id=assigned)


def test_actor_capabilities_gate_on_assignment_identity():
    step = _step(assigned_role_key="a", supervisor_role="s")
    db = _FakeDB(step)
    # holds the actor role_key but is NOT the assignee → no actor caps
    caps = capabilities_for_user_on_ticket(db, _ticket(assigned="someone_else"), _user(["a"]))
    assert "tickets:resolve" not in caps
    # is the assignee → holds actor caps regardless of role_key backing
    caps = capabilities_for_user_on_ticket(db, _ticket(assigned="u1"), _user([], uid="u1"))
    assert {"tickets:acknowledge", "tickets:escalate", "tickets:resolve"} <= caps


def test_supervisor_capabilities_gate_on_tier_membership():
    step = _step(assigned_role_key="a", supervisor_role="s")
    db = _FakeDB(step)
    caps = capabilities_for_user_on_ticket(db, _ticket(assigned="nobody"), _user(["s"]))
    assert {"tickets:resolve", "tickets:reassign"} <= caps
    assert "tickets:acknowledge" in caps


def test_participant_and_observer_axes():
    step = _step(assigned_role_key="a", informed_roles=["p"], observer_roles=["o"])
    db = _FakeDB(step)
    p_caps = capabilities_for_user_on_ticket(db, _ticket(assigned="nobody"), _user(["p"]))
    assert p_caps == {"tickets:read", "tickets:note"}
    o_caps = capabilities_for_user_on_ticket(db, _ticket(assigned="nobody"), _user(["o"]))
    assert o_caps == {"tickets:read"}


def test_admin_holds_all_operational_capabilities():
    step = _step()
    db = _FakeDB(step)
    caps = capabilities_for_user_on_ticket(db, _ticket(), _user([], is_admin=True))
    assert {"tickets:resolve", "tickets:reassign", "tickets:note", "tickets:read"} <= caps
